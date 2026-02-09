#!/usr/bin/env python3
"""
Parallel Executor - Diamond Architecture Parallel Deliberation Layer

Implements Council v2.0 Phase 1 requirement: Parallel model execution
for the Diamond Architecture pattern.

Execution Pattern:
  Stage 1 (PARALLEL): kimi + perplexity → context gathering
  Stage 2 (PARALLEL): deepseek + gemini-flash + sonnet → deliberation
  Stage 3 (SEQUENTIAL): gemini-pro → synthesis
  Stage 4 (CONDITIONAL): opus → ratification
"""

import os
import sys
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import gateway for model calls
try:
    from skills.council.scripts.gateway import get_gateway
    from skills.council.scripts.models import MODEL_FALLBACKS
except ImportError:
    # Fallback if skills not in path
    def get_gateway():
        return "http://localhost:4000/v1/chat/completions"
    MODEL_FALLBACKS = {}

# Import Perplexity wrapper for web research
try:
    from skills.council.scripts.perplexity_wrapper import PerplexityWrapper, PerplexityResponse
except ImportError:
    PerplexityWrapper = None
    PerplexityResponse = None


@dataclass
class ModelResponse:
    """Response from a single model execution."""
    model: str
    content: str
    success: bool
    latency_seconds: float
    cost: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None
    fallback_used: Optional[str] = None


@dataclass
class ParallelResult:
    """Results from parallel model execution."""
    responses: List[ModelResponse]
    total_latency: float
    total_cost: float
    total_tokens: int
    success_count: int
    failure_count: int

    def get_successful_responses(self) -> List[ModelResponse]:
        """Get only successful responses."""
        return [r for r in self.responses if r.success]

    def get_model_content(self, model: str) -> Optional[str]:
        """Get content from a specific model."""
        for r in self.responses:
            if r.model == model and r.success:
                return r.content
        return None

    def format_for_synthesis(self) -> str:
        """Format responses for input to synthesizer model."""
        output = ["## Parallel Deliberation Results\n"]

        for r in self.responses:
            if r.success:
                output.append(f"### {r.model}\n{r.content}\n")
            else:
                output.append(f"### {r.model} (FAILED)\nError: {r.error}\n")

        return "\n".join(output)


@dataclass
class DiamondDebateResult:
    """
    Results from sequential Diamond debate workflow.

    This is the 4-step sequential workflow from team-debate-4step.ps1:
    Step 1: Architect (gemini-architect) → proposes solution
    Step 2: Auditor (deepseek-v3) → critiques proposal
    Step 3: Contextualist (kimi-researcher) → codebase-aware analysis
    Step 4: Judge (opus-synthesis) → final decree
    """
    step1_architect: ModelResponse
    step2_auditor: ModelResponse
    step3_contextualist: ModelResponse
    step4_judge: ModelResponse
    total_latency: float
    total_cost: float
    total_tokens: int

    def get_proposal(self) -> str:
        """Get the Architect's proposal."""
        return self.step1_architect.content if self.step1_architect.success else ""

    def get_critique(self) -> str:
        """Get the Auditor's critique."""
        return self.step2_auditor.content if self.step2_auditor.success else ""

    def get_contextual_analysis(self) -> str:
        """Get the Contextualist's analysis."""
        return self.step3_contextualist.content if self.step3_contextualist.success else ""

    def get_final_decree(self) -> str:
        """Get the Judge's final decree."""
        return self.step4_judge.content if self.step4_judge.success else ""

    def format_summary(self) -> str:
        """Format a summary of the debate results."""
        output = [
            "## Diamond Debate Summary\n",
            f"Total Time: {self.total_latency:.2f}s",
            f"Total Cost: ${self.total_cost:.4f}",
            f"Total Tokens: {self.total_tokens}\n",
            "### Step Timings:",
            f"  Architect: {self.step1_architect.latency_seconds:.2f}s",
            f"  Auditor: {self.step2_auditor.latency_seconds:.2f}s",
            f"  Contextualist: {self.step3_contextualist.latency_seconds:.2f}s",
            f"  Judge: {self.step4_judge.latency_seconds:.2f}s\n",
        ]
        return "\n".join(output)


class ParallelExecutor:
    """
    Executes multiple models in parallel for Diamond Architecture.

    Supports the Council v2.0 workflow pattern:
    - Stage 1: kimi + perplexity (context gathering)
    - Stage 2: deepseek + gemini-flash + sonnet (deliberation)
    - Stage 3: gemini-pro (synthesis)
    - Stage 4: opus (conditional ratification)
    """

    # Default timeout for each model (seconds)
    DEFAULT_TIMEOUT = 120

    # Gateway URL
    GATEWAY_URL = "http://localhost:4000/v1/chat/completions"

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        max_workers: int = 5,
        default_timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize the parallel executor.

        Args:
            gateway_url: LiteLLM gateway URL (default: localhost:4000)
            max_workers: Maximum parallel threads
            default_timeout: Default timeout for each model call
        """
        self.gateway_url = gateway_url or self.GATEWAY_URL
        self.max_workers = max_workers
        self.default_timeout = default_timeout

        # Perplexity wrapper (for perplexity-* models)
        self.perplexity = PerplexityWrapper() if PerplexityWrapper else None

    def _execute_model(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        timeout: Optional[int] = None
    ) -> ModelResponse:
        """
        Execute a single model.

        Args:
            model: Model name/alias
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            timeout: Request timeout

        Returns:
            ModelResponse with results
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout

        # Check if this is a Perplexity model (direct API call)
        if model.startswith("perplexity-") and self.perplexity:
            try:
                perplexity_model = "sonar-small-online" if model == "perplexity-researcher" else "sonar-medium-online"
                result = self.perplexity.search(prompt, model=perplexity_model, timeout=timeout)

                # Format Perplexity results as content
                content = f"## Web Research Results\n\n"
                if result.answer:
                    content += f"{result.answer}\n\n"

                content += f"### Sources ({len(result.citations)})\n"
                for i, citation in enumerate(result.citations, 1):
                    content += f"{i}. [{citation.title}]({citation.url})\n"

                return ModelResponse(
                    model=model,
                    content=content,
                    success=True,
                    latency_seconds=result.latency_seconds,
                    cost=result.cost,
                    tokens_used=result.tokens_used,
                )
            except Exception as e:
                return ModelResponse(
                    model=model,
                    content="",
                    success=False,
                    latency_seconds=time.time() - start_time,
                    error=str(e)
                )

        # Regular LLM model via gateway
        try:
            import requests

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            }

            response = requests.post(
                self.gateway_url,
                json=payload,
                timeout=timeout
            )

            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            # Estimate cost (would use pricing module in production)
            tokens_used = usage.get("total_tokens", 0)
            cost = self._estimate_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

            return ModelResponse(
                model=model,
                content=content,
                success=True,
                latency_seconds=time.time() - start_time,
                cost=cost,
                tokens_used=tokens_used,
            )

        except requests.exceptions.Timeout:
            # Try fallback if available
            fallback = MODEL_FALLBACKS.get(model)
            if fallback and fallback != model:
                return self._execute_model(fallback, prompt, system_prompt, max_tokens, timeout)

            return ModelResponse(
                model=model,
                content="",
                success=False,
                latency_seconds=timeout,
                error=f"Timeout after {timeout}s"
            )

        except Exception as e:
            # Try fallback if available
            fallback = MODEL_FALLBACKS.get(model)
            if fallback and fallback != model:
                result = self._execute_model(fallback, prompt, system_prompt, max_tokens, timeout)
                result.fallback_used = model
                result.model = f"{model} (via {fallback})"
                return result

            return ModelResponse(
                model=model,
                content="",
                success=False,
                latency_seconds=time.time() - start_time,
                error=str(e)
            )

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for a model call."""
        # Simple cost estimation (would use pricing module)
        # Conservative estimates per 1M tokens
        pricing = {
            "claude-sonnet": (3.0, 15.0),
            "deepseek-v3": (0.27, 1.10),
            "gemini-flash": (0.075, 0.30),
            "kimi-researcher": (1.20, 12.0),
            "gemini-pro": (0.075, 0.30),
            "opus-synthesis": (15.0, 75.0),
        }

        if model in pricing:
            input_price, output_price = pricing[model]
            return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price

        return 0.01  # Default estimate

    def execute_parallel(
        self,
        models: List[str],
        prompt: str,
        system_prompts: Optional[Dict[str, str]] = None,
        max_tokens: int = 2000,
        timeout: Optional[int] = None
    ) -> ParallelResult:
        """
        Execute multiple models in parallel.

        Args:
            models: List of model names to execute
            prompt: Common prompt for all models
            system_prompts: Optional dict of model-specific system prompts
            max_tokens: Maximum tokens per model
            timeout: Timeout for each model

        Returns:
            ParallelResult with all responses
        """
        system_prompts = system_prompts or {}
        start_time = time.time()

        responses = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(models))) as executor:
            # Submit all tasks
            future_to_model = {
                executor.submit(
                    self._execute_model,
                    model,
                    prompt,
                    system_prompts.get(model),
                    max_tokens,
                    timeout
                ): model
                for model in models
            }

            # Collect results as they complete
            for future in as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    response = future.result()
                    responses.append(response)
                except Exception as e:
                    responses.append(ModelResponse(
                        model=model,
                        content="",
                        success=False,
                        latency_seconds=0,
                        error=f"Execution error: {e}"
                    ))

        total_latency = time.time() - start_time

        # Calculate totals
        total_cost = sum(r.cost for r in responses)
        total_tokens = sum(r.tokens_used for r in responses)
        success_count = sum(1 for r in responses if r.success)
        failure_count = len(responses) - success_count

        return ParallelResult(
            responses=responses,
            total_latency=total_latency,
            total_cost=total_cost,
            total_tokens=total_tokens,
            success_count=success_count,
            failure_count=failure_count,
        )

    def execute_stage(
        self,
        stage_name: str,
        prompt: str,
        models: Optional[List[str]] = None,
        **kwargs
    ) -> ParallelResult:
        """
        Execute a predefined Diamond Architecture stage.

        Args:
            stage_name: Stage name ("stage1_context", "stage2_deliberate", "stage3_synthesize")
            prompt: Prompt for this stage
            models: Optional override of default models for this stage
            **kwargs: Additional arguments for execute_parallel

        Returns:
            ParallelResult for this stage
        """
        # Default model configurations for each stage
        stage_configs = {
            "stage1_context": {
                "models": ["kimi-researcher", "perplexity-online"],
                "system_prompts": {
                    "kimi-researcher": "You are a Cost Architect. Analyze the query for cost-benefit, propose technical solutions, and identify key components.",
                    "perplexity-online": "You are a web research assistant. Find the latest information about the query.",
                },
                "max_tokens": 1500,
            },
            "stage2_deliberate": {
                "models": ["deepseek-v3", "gemini-flash", "claude-sonnet"],
                "system_prompts": {
                    "deepseek-v3": "You are an Auditor. Critique the proposal for security risks, logic flaws, edge cases, and scalability issues. Identify BLOCKER issues prominently.",
                    "gemini-flash": "You are an Ideator. Generate creative solutions and alternatives. Think fast and be thorough.",
                    "claude-sonnet": "You are a Contextualist. Check existing codebase patterns, identify integration points, and what can be reused.",
                },
                "max_tokens": 2000,
            },
            "stage3_synthesize": {
                "models": ["gemini-pro"],
                "system_prompts": {
                    "gemini-pro": "You are the Semi-Final Judge. Synthesize all perspectives and provide your assessment. Identify remaining concerns and recommend approval path (APPROVED, CONDITIONAL, NEEDS_DEBATE).",
                },
                "max_tokens": 3000,
            },
        }

        if stage_name not in stage_configs:
            raise ValueError(f"Unknown stage: {stage_name}")

        config = stage_configs[stage_name]
        models = models or config["models"]
        system_prompts = kwargs.get("system_prompts", config["system_prompts"])
        max_tokens = kwargs.get("max_tokens", config["max_tokens"])

        return self.execute_parallel(
            models=models,
            prompt=prompt,
            system_prompts=system_prompts,
            max_tokens=max_tokens,
            timeout=kwargs.get("timeout"),
        )


# ============================================================================
# Diamond Architecture Orchestrator
# ============================================================================

class DiamondOrchestrator:
    """
    Orchestrates the full Diamond Architecture workflow.

    Pattern:
      Stage 1 (PARALLEL): kimi + perplexity → context
      Stage 2 (PARALLEL): deepseek + gemini-flash + sonnet → deliberation
      Stage 3 (SEQUENTIAL): gemini-pro → synthesis
      Stage 4 (CONDITIONAL): opus → ratification
    """

    def __init__(self, executor: Optional[ParallelExecutor] = None):
        self.executor = executor or ParallelExecutor()

    def execute_diamond(
        self,
        query: str,
        context: str = "",
        invoke_opus: bool = False,
        opus_threshold: str = "conditional"
    ) -> Dict[str, Any]:
        """
        Execute the full Diamond Architecture.

        Args:
            query: The user's query
            context: Additional context (file contents, etc.)
            invoke_opus: Whether to invoke Opus for final ratification
            opus_threshold: When to invoke Opus ("always", "conditional", "never")

        Returns:
            Dict with stage results and final recommendation
        """
        full_prompt = f"Query: {query}\n\n{context}".strip()

        results = {
            "query": query,
            "stages": {},
            "final_recommendation": None,
            "total_cost": 0,
            "total_latency": 0,
        }

        # Stage 1: Context Acquisition (Parallel)
        stage1 = self.executor.execute_stage("stage1_context", full_prompt)
        results["stages"]["context"] = stage1
        results["total_cost"] += stage1.total_cost

        # Build prompt for Stage 2 with Stage 1 context
        stage2_prompt = f"""Original Query: {query}

Context from Stage 1:
{stage1.format_for_synthesis()}

Please analyze this proposal based on your role."""
        # Stage 2: Deliberation (Parallel)
        stage2 = self.executor.execute_stage("stage2_deliberate", stage2_prompt)
        results["stages"]["deliberation"] = stage2
        results["total_cost"] += stage2.total_cost

        # Build prompt for Stage 3 with Stage 2 deliberation
        stage3_prompt = f"""Original Query: {query}

Deliberation Results:
{stage2.format_for_synthesis()}

As Semi-Final Judge, synthesize all perspectives and provide:
1. Your assessment of the approach
2. Any remaining concerns or gaps
3. Recommendation: APPROVED (ready for Opus), CONDITIONAL (fix X first), NEEDS_DEBATE (major concerns)"""
        # Stage 3: Synthesis (Sequential)
        stage3 = self.executor.execute_stage("stage3_synthesize", stage3_prompt)
        results["stages"]["synthesis"] = stage3
        results["total_cost"] += stage3.total_cost

        # Extract recommendation from synthesis
        synthesis_content = stage3.get_model_content("gemini-pro") or ""
        results["final_recommendation"] = self._extract_recommendation(synthesis_content)

        # Stage 4: Opus Ratification (Conditional)
        if invoke_opus and self._should_invoke_opus(results["final_recommendation"], opus_threshold):
            stage4_prompt = f"""Original Query: {query}

Semi-Final Assessment:
{synthesis_content}

As Final Judge, issue your decree:
1. APPROVED - Ready to build
2. CONDITIONAL - Fix X first
3. REJECTED - Not viable

Provide clear rationale and implementation phases."""

            stage4 = self.executor.execute_parallel(
                models=["opus-synthesis"],
                prompt=stage4_prompt,
                system_prompts={"opus-synthesis": "You are the Final Judge. Review the semi-final assessment and issue a final decree with clear rationale."},
                max_tokens=4000,
            )
            results["stages"]["ratification"] = stage4
            results["total_cost"] += stage4.total_cost

            # Update final recommendation with Opus's decision
            opus_content = stage4.get_model_content("opus-synthesis") or ""
            results["final_recommendation"] = self._extract_recommendation(opus_content)
            results["opus_decision"] = opus_content

        results["total_latency"] = sum(
            s.total_latency for s in results["stages"].values()
        )

        return results

    def _extract_recommendation(self, content: str) -> str:
        """Extract recommendation from model content."""
        content_upper = content.upper()

        if "APPROVED" in content_upper and "CONDITIONAL" not in content_upper:
            return "APPROVED"
        elif "REJECTED" in content_upper:
            return "REJECTED"
        elif "CONDITIONAL" in content_upper or "NEEDS_DEBATE" in content_upper:
            return "CONDITIONAL"
        else:
            return "UNCLEAR"

    def _should_invoke_opus(self, recommendation: str, threshold: str) -> bool:
        """Determine if Opus should be invoked."""
        if threshold == "always":
            return True
        if threshold == "never":
            return False
        if threshold == "conditional":
            # Invoke Opus if not clearly approved
            return recommendation != "APPROVED"
        return False

    def execute_diamond_debate(
        self,
        topic: str,
        focus: Optional[str] = None,
        context: str = ""
    ) -> DiamondDebateResult:
        """
        Execute the 4-step sequential Diamond debate workflow.

        This is the team-debate-4step.ps1 workflow:
        Step 1: Architect (gemini-architect) → proposes solution
        Step 2: Auditor (deepseek-v3) → critiques proposal
        Step 3: Contextualist (kimi-researcher) → codebase-aware analysis
        Step 4: Judge (opus-synthesis) → final decree

        Each step sees the previous steps' output (sequential, not parallel).

        Args:
            topic: The topic or problem statement for the debate
            focus: Optional focus area (security, scalability, cost, performance, etc.)
            context: Additional context (file contents, codebase info, etc.)

        Returns:
            DiamondDebateResult with all 4 steps' responses
        """
        focus_prompt = f" Focus your analysis on: {focus}." if focus else ""

        # Step 1: Architect (Gemini 3 Pro)
        step1_prompt = f"""You are the Architect. Propose a high-level technical solution for: {topic}

{focus_prompt}

Structure your response as:
1) Problem Statement
2) Recommended Approach
3) Key Components
4) Potential Risks

Be concise but thorough."""

        step1 = self.executor._execute_model(
            model="gemini-architect",
            prompt=step1_prompt,
            max_tokens=3000,
            timeout=60
        )

        if not step1.success:
            # If architect fails, return early with error
            return DiamondDebateResult(
                step1_architect=step1,
                step2_auditor=ModelResponse("deepseek-v3", "", False, 0, 0, 0, error="Architect failed, skipping"),
                step3_contextualist=ModelResponse("kimi-researcher", "", False, 0, 0, 0, error="Architect failed, skipping"),
                step4_judge=ModelResponse("opus-synthesis", "", False, 0, 0, 0, error="Architect failed, skipping"),
                total_latency=step1.latency_seconds,
                total_cost=step1.cost,
                total_tokens=step1.tokens_used,
            )

        # Step 2: Auditor (DeepSeek V3)
        step2_prompt = f"""You are the Auditor. Critique this proposal for security, logic flaws, and edge cases. Be thorough but constructive.

PROPOSAL:
{step1.content}

Focus on:
1) Security vulnerabilities
2) Logic flaws or edge cases
3) Scalability concerns
4) Missing considerations

Provide specific, actionable critique."""

        step2 = self.executor._execute_model(
            model="deepseek-v3",
            prompt=step2_prompt,
            max_tokens=4000,
            timeout=90
        )

        # Step 3: Contextualist (Kimi K2 Turbo)
        step3_prompt = f"""You are the Contextualist with 256k context awareness. Analyze this proposal and critique from the perspective of: existing codebase patterns, integration points, historical decisions, and project context.

PROPOSAL:
{step1.content}

AUDITOR'S CRITIQUE:
{step2.content}

Provide:
1) Connection to existing codebase patterns
2) Integration points with current system
3) Edge cases from project history
4) Recommendations for alignment with current architecture

Be specific about what already exists in the codebase that should be leveraged or followed.

{context if context else ""}"""

        step3 = self.executor._execute_model(
            model="kimi-researcher",
            prompt=step3_prompt,
            max_tokens=5000,
            timeout=180
        )

        # Step 4: Judge (Claude Opus)
        step4_prompt = f"""You are the Supreme Court Judge. Synthesize a final decision based on this proposal, critique, and context-aware analysis.

PROPOSAL:
{step1.content}

AUDITOR'S CRITIQUE:
{step2.content}

CONTEXTUALIST'S ANALYSIS:
{step3.content}

Weigh all perspectives and issue a final decree with:
1) Analysis of key points
2) Accepted recommendations
3) Final decision or implementation plan

Be decisive and actionable."""

        step4 = self.executor._execute_model(
            model="opus-synthesis",
            prompt=step4_prompt,
            max_tokens=64000,
            timeout=180
        )

        # Calculate totals
        total_latency = sum([
            step1.latency_seconds,
            step2.latency_seconds,
            step3.latency_seconds,
            step4.latency_seconds,
        ])
        total_cost = sum([
            step1.cost,
            step2.cost,
            step3.cost,
            step4.cost,
        ])
        total_tokens = sum([
            step1.tokens_used,
            step2.tokens_used,
            step3.tokens_used,
            step4.tokens_used,
        ])

        return DiamondDebateResult(
            step1_architect=step1,
            step2_auditor=step2,
            step3_contextualist=step3,
            step4_judge=step4,
            total_latency=total_latency,
            total_cost=total_cost,
            total_tokens=total_tokens,
        )


# ============================================================================
# CLI Testing
# ============================================================================
if __name__ == "__main__":
    import json

    orchestrator = DiamondOrchestrator()

    print("=== Diamond Architecture Test ===\n")

    test_query = "Should we use PostgreSQL or MongoDB for this project?"

    print(f"Query: {test_query}\n")

    result = orchestrator.execute_diamond(
        query=test_query,
        invoke_opus=True,
        opus_threshold="conditional"
    )

    print(f"Final Recommendation: {result['final_recommendation']}")
    print(f"Total Cost: ${result['total_cost']:.4f}")
    print(f"Total Latency: {result['total_latency']:.2f}s\n")

    for stage_name, stage_result in result["stages"].items():
        print(f"## {stage_name.upper()}")
        print(f"  Success: {stage_result.success_count}/{len(stage_result.responses)}")
        print(f"  Cost: ${stage_result.total_cost:.4f}")
        print(f"  Latency: {stage_result.total_latency:.2f}s")
        print()
