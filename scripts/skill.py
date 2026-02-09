#!/usr/bin/env python3
"""
Council Multi-Tiered AI Collaboration System - Skill Entry Point

Routes requests to appropriate Council mode based on first argument:
- brainstorm: Generate diverse ideas (parallel models)
- refine: Critical review and improvement (sequential with quality gates)
- build-plan: Detailed technical specifications (full Council workflow)
- build-review: Post-build validation (review against criteria)
- opus-gatekeeper: Cost optimization for Opus invocation
- diamond-debate: Complex architectural decisions (parallel architecture)
- team-debate: Build specifications (sequential workflow)

Usage:
    python skill.py brainstorm <prompt>
    python skill.py refine <input_text>
    python skill.py build-plan <topic>
    python skill.py build-review <implementation_summary>
    python skill.py opus-gatekeeper <query>
    python skill.py diamond-debate <topic>
    python skill.py team-debate <topic>

OUTPUT SAVING: All 7 modes save their output to skills/council/build-plans/
Version: 2.1.1 (Priority 1 fix complete - all modes now save output)
"""

import sys
import json
from pathlib import Path

# Bootstrap: Add project root to sys.path for absolute imports
# This allows skill.py to be run directly or imported
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now we can use absolute imports
scripts_dir = Path(__file__).parent

# Import Council modules
try:
    from brainstorm import brainstorm
    from build_planner import build_planner
    from build_reviewer import review_build
    from opus_gatekeeper import OpusGatekeeper
    from parallel_executor import DiamondOrchestrator
except ImportError as e:
    print(f"Error importing Council modules: {e}", file=sys.stderr)
    sys.exit(1)


def print_banner(mode: str):
    """Print Council banner for mode."""
    banners = {
        "brainstorm": "⚡ Council Brainstorming Mode",
        "refine": "🔍 Council Refinement Mode",
        "build-plan": "🏗️  Council Build Planning Mode",
        "build-review": "✅ Council Build Reviewer Mode",
        "opus-gatekeeper": "🚪 Council Opus Gatekeeper Mode",
        "diamond-debate": "💎 Council Diamond Debate Mode",
        "team-debate": "🏛️  Council Team Debate Mode"
    }
    print(f"\n{banners.get(mode, 'Council Mode')}")
    print("=" * 60)


# =============================================================================
# COUNCIL OUTPUT SAVING (Priority 1 Fix)
# =============================================================================

def save_council_output(mode: str, content: str, prompt_summary: str = "") -> str:
    """
    Save Council output to build-plans/ directory.

    Shared function for all Council modes to ensure consistent output saving.

    Args:
        mode: Council mode name (brainstorm, refine, etc.)
        content: Full output content to save
        prompt_summary: Brief summary of the input/prompt for filename

    Returns:
        Path to saved file, or None if save failed
    """
    try:
        from paths import get_build_plans_dir, sanitize_filename, ensure_directories
        from datetime import datetime

        ensure_directories()

        # Create filename: timestamp-mode-summary.md
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Sanitize summary for filename (limit to 40 chars, remove special chars)
        safe_summary = sanitize_filename(prompt_summary[:40] if prompt_summary else "output")
        filename = f"{timestamp}-{mode}-{safe_summary}.md"

        artifact_path = get_build_plans_dir() / filename

        # Add header to content
        full_content = f"""# Council {mode.title()} Output

**Generated:** {datetime.now().isoformat()}
**Mode:** {mode}
**Prompt:** {prompt_summary[:100] if prompt_summary else 'N/A'}

---

{content}
"""

        # Write to file
        artifact_path.write_text(full_content, encoding="utf-8")

        print(f"\n✓ Council {mode} output saved to: {artifact_path.name}")
        return str(artifact_path)

    except Exception as e:
        print(f"\n⚠ Warning: Could not save {mode} output: {e}", file=sys.stderr)
        return None


def mode_brainstorm(prompt: str, max_ideas: int = 10):
    """Run brainstorming mode."""
    print_banner("brainstorm")
    print(f"Prompt: {prompt[:100]}...\n")

    result = brainstorm(prompt, max_ideas=max_ideas)

    if result["success"]:
        print(f"\n✓ Generated {result['count']} ideas:\n")
        for i, idea in enumerate(result["ideas"], 1):
            category = idea.get("category", "General")
            desc = idea["description"][:200]
            print(f"{i}. [{category}] {desc}...")

        # Save output
        output_content = f"Generated {result['count']} ideas:\n\n"
        for i, idea in enumerate(result["ideas"], 1):
            category = idea.get("category", "General")
            desc = idea["description"]
            output_content += f"{i}. [{category}] {desc}\n"

        save_council_output("brainstorm", output_content, prompt)

        return 0
    else:
        print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
        return 1


def mode_refine(input_text: str, context: str = ""):
    """Run refinement mode."""
    print_banner("refine")
    print(f"Input: {input_text[:100]}...\n")

    # Import refine module
    try:
        from refine import refine
        result = refine(input_text, context=context)

        if result["success"]:
            print("\n✓ Refinement complete:\n")
            print(result["refined_output"][:500] + "...")

            if result.get("critiques"):
                print("\nCritiques:")
                for critique in result["critiques"]:
                    print(f"  - {critique.get('model', 'Unknown')}: {critique.get('summary', 'No summary')}")

            # Save output
            output_content = f"Input: {input_text[:200]}...\n\n"
            output_content += f"Refined Output:\n{result['refined_output']}\n\n"

            if result.get("critiques"):
                output_content += "Critiques:\n"
                for critique in result.get("critiques", []):
                    output_content += f"- {critique.get('model', 'Unknown')}: {critique.get('summary', 'No summary')}\n"

            save_council_output("refine", output_content, input_text[:40])

            return 0
        else:
            print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
            return 1
    except ImportError as e:
        print(f"Error: Refinement mode not available: {e}")
        return 1


def mode_build_plan(topic: str, context: str = ""):
    """Run build planning mode."""
    print_banner("build-plan")
    print(f"Topic: {topic[:100]}...\n")

    result = build_planner(topic, context=context)

    if result["success"]:
        plan = result["build_plan"]
        print(f"\n✓ Status: {plan['status']}")
        print(f"✓ Artifact: {result.get('artifact_path', 'N/A')}")

        decisions = plan.get("council_decisions", {})
        print(f"\nArchitect: {decisions.get('architect', 'N/A')[:100]}...")
        print(f"Judge: {decisions.get('judge_decision', 'N/A')}")

        if plan.get("implementation_plan"):
            print(f"\nImplementation Plan:")
            for step in plan["implementation_plan"][:3]:
                print(f"  - {step}")
        return 0
    else:
        print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
        return 1


def mode_build_review(implementation_summary: str, build_plan_path: str = None):
    """Run build review mode."""
    print_banner("build-review")
    print(f"Reviewing implementation...\n")

    if build_plan_path:
        # Review against build plan
        result = review_build(
            build_plan_path=build_plan_path,
            implementation_summary=implementation_summary
        )
    else:
        # Quick review without plan
        from build_reviewer import quick_review
        result = quick_review(
            what_was_built=implementation_summary,
            criteria=[
                "Requirements met",
                "Code quality",
                "Security",
                "Error handling"
            ]
        )

    if result["success"]:
        print(f"\n✓ Verdict: {result['recommendation']}")

        # Save output to build-plans/ (not build-reviews/)
        output_content = f"Verdict: {result['recommendation']}\n\n"

        if result.get("passed_checks"):
            output_content += "Passed Checks:\n"
            for check in result.get("passed_checks", []):
                output_content += f"  ✓ {check}\n"

        if result.get("failed_checks"):
            output_content += "Failed Checks:\n"
            for check in result.get("failed_checks", []):
                output_content += f"  ✗ {check}\n"

        save_council_output("build-review", output_content, implementation_summary[:40])

        if result.get("passed_checks"):
            print(f"\nPassed ({len(result['passed_checks'])}):")
            for check in result["passed_checks"][:3]:
                print(f"  ✓ {check}")

        if result.get("failed_checks"):
            print(f"\nFailed ({len(result['failed_checks'])}):")
            for check in result["failed_checks"][:3]:
                print(f"  ✗ {check}")
        return 0
    else:
        print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
        return 1


def mode_opus_gatekeeper(query: str, monthly_budget: float = 100.0, current_spend: float = 0.0):
    """Run Opus gatekeeper mode."""
    print_banner("opus-gatekeeper")
    print(f"Query: {query[:100]}...\n")

    gatekeeper = OpusGatekeeper(
        monthly_budget=monthly_budget,
        current_monthly_spend=current_spend
    )

    result = gatekeeper.should_invoke_opus(query)

    print(f"Decision: {result.decision.value}")
    print(f"Category: {result.category}")
    print(f"Tier: {result.tier}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Reason: {result.reason}")
    print(f"Budget Remaining: ${result.budget_remaining:.2f} / ${monthly_budget:.2f}")

    if result.decision.value != "INVOKE":
        alternative = gatekeeper.recommend_degradation(result)
        if alternative:
            print(f"\n→ Recommended Alternative: {alternative}")
        else:
            print(f"\n→ No alternative needed (skip Opus)")

    # Save output
    output_content = f"""Decision: {result.decision.value}
Category: {result.category}
Tier: {result.tier}
Confidence: {result.confidence:.0%}
Reason: {result.reason}
Budget Remaining: ${result.budget_remaining:.2f} / ${monthly_budget:.2f}
"""
    if result.decision.value != "INVOKE":
        alternative = gatekeeper.recommend_degradation(result)
        if alternative:
            output_content += f"\nRecommended Alternative: {alternative}\n"
        else:
            output_content += "\nNo alternative needed (skip Opus)\n"

    save_council_output("opus-gatekeeper", output_content, query[:40])

    return 0 if result.decision.value in ["INVOKE", "SKIP"] else 1


def mode_diamond_debate(topic: str, focus: str = "", context: str = ""):
    """
    Run Diamond Debate mode using Diamond Architecture (parallel stages).

    This uses the DiamondOrchestrator.execute_diamond() method which implements:
    - Stage 1 (PARALLEL): kimi + perplexity → context gathering
    - Stage 2 (PARALLEL): deepseek + gemini-flash + sonnet → deliberation
    - Stage 3 (SEQUENTIAL): gemini-pro → synthesis
    - Stage 4 (CONDITIONAL): opus → ratification
    """
    print_banner("diamond-debate")
    print(f"Topic: {topic[:100]}...")
    if focus:
        print(f"Focus: {focus}")
    print()

    orchestrator = DiamondOrchestrator()

    # Build context string
    full_context = f"Focus: {focus}\n\n{context}" if focus else context

    # Execute Diamond Architecture
    result = orchestrator.execute_diamond(
        query=topic,
        context=full_context,
        invoke_opus=True,  # Always invoke Opus for final ratification
        opus_threshold="conditional"
    )

    # Display results
    print(f"\n{'='*60}")
    print("💎 DIAMOND DEBATE RESULTS")
    print(f"{'='*60}\n")

    # Stage 1: Context Acquisition
    stage1 = result["stages"].get("context")
    if stage1:
        print("1️⃣  Stage 1: Context Acquisition (Parallel)")
        print(f"   Models: kimi-researcher + perplexity-online")
        print(f"   Time: {stage1.total_latency:.2f}s | Cost: ${stage1.total_cost:.4f}")
        print(f"   Success: {stage1.success_count}/{len(stage1.responses)}")
        for response in stage1.get_successful_responses():
            preview = response.content[:150].replace('\n', ' ')
            print(f"\n   📌 {response.model}:")
            print(f"      {preview}...")

    # Stage 2: Deliberation
    stage2 = result["stages"].get("deliberation")
    if stage2:
        print(f"\n2️⃣  Stage 2: Deliberation (Parallel)")
        print(f"   Models: deepseek-v3 + gemini-flash + claude-sonnet")
        print(f"   Time: {stage2.total_latency:.2f}s | Cost: ${stage2.total_cost:.4f}")
        print(f"   Success: {stage2.success_count}/{len(stage2.responses)}")
        for response in stage2.get_successful_responses():
            preview = response.content[:150].replace('\n', ' ')
            print(f"\n   📌 {response.model}:")
            print(f"      {preview}...")

    # Stage 3: Synthesis
    stage3 = result["stages"].get("synthesis")
    if stage3:
        synthesis = stage3.get_model_content("gemini-pro")
        print(f"\n3️⃣  Stage 3: Semi-Final Synthesis (gemini-pro)")
        print(f"   Time: {stage3.total_latency:.2f}s | Cost: ${stage3.total_cost:.4f}")
        if synthesis:
            preview = synthesis[:300].replace('\n', ' ')
            print(f"\n   {preview}...")

    # Stage 4: Opus Ratification
    stage4 = result["stages"].get("ratification")
    if stage4:
        decree = stage4.get_model_content("opus-synthesis")
        print(f"\n4️⃣  Stage 4: Final Ratification (opus-synthesis)")
        print(f"   Time: {stage4.total_latency:.2f}s | Cost: ${stage4.total_cost:.4f}")
        if decree:
            print(f"\n{'─'*60}")
            print("🏛️  FINAL COUNCIL DECREE")
            print(f"{'─'*60}")
            print(decree)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total Time: {result['total_latency']:.2f}s")
    print(f"Total Cost: ${result['total_cost']:.4f}")
    print(f"Recommendation: {result['final_recommendation']}")
    print()

    # Save output
    output_content = f"""Total Time: {result['total_latency']:.2f}s
Total Cost: ${result['total_cost']:.4f}
Recommendation: {result['final_recommendation']}

---

## Stage 1: Context Acquisition (Parallel)
Models: kimi-researcher + perplexity-online
"""
    stage1 = result["stages"].get("context")
    if stage1:
        output_content += f"Time: {stage1.total_latency:.2f}s | Cost: ${stage1.total_cost:.4f}\n"
        output_content += f"Success: {stage1.success_count}/{len(stage1.responses)}\n\n"
        for response in stage1.get_successful_responses():
            output_content += f"\n### {response.model}\n{response.content}\n"

    output_content += "\n---\n\n## Stage 2: Deliberation (Parallel)\nModels: deepseek-v3 + gemini-flash + claude-sonnet\n"
    stage2 = result["stages"].get("deliberation")
    if stage2:
        output_content += f"Time: {stage2.total_latency:.2f}s | Cost: ${stage2.total_cost:.4f}\n"
        output_content += f"Success: {stage2.success_count}/{len(stage2.responses)}\n\n"
        for response in stage2.get_successful_responses():
            output_content += f"\n### {response.model}\n{response.content}\n"

    output_content += "\n---\n\n## Stage 3: Semi-Final Synthesis (gemini-pro)\n"
    stage3 = result["stages"].get("synthesis")
    if stage3:
        synthesis = stage3.get_model_content("gemini-pro")
        output_content += f"Time: {stage3.total_latency:.2f}s | Cost: ${stage3.total_cost:.4f}\n\n"
        if synthesis:
            output_content += f"{synthesis}\n"

    output_content += "\n---\n\n## Stage 4: Final Ratification (opus-synthesis)\n"
    stage4 = result["stages"].get("ratification")
    if stage4:
        decree = stage4.get_model_content("opus-synthesis")
        output_content += f"Time: {stage4.total_latency:.2f}s | Cost: ${stage4.total_cost:.4f}\n\n"
        if decree:
            output_content += f"## FINAL COUNCIL DECREE\n\n{decree}\n"

    save_council_output("diamond-debate", output_content, topic[:40])

    return 0


def mode_team_debate(topic: str, focus: str = "", context: str = ""):
    """
    Run Team Debate mode using sequential 4-step workflow.

    This uses the DiamondOrchestrator.execute_diamond_debate() method which implements:
    - Step 1: Architect (gemini-architect) → proposes solution
    - Step 2: Auditor (deepseek-v3) → critiques proposal
    - Step 3: Contextualist (kimi-researcher) → codebase-aware analysis
    - Step 4: Judge (opus-synthesis) → final decree

    This is the same workflow as team-debate-4step.ps1, providing sequential
    refinement where each step builds on the previous output.
    """
    from datetime import datetime
    from paths import get_build_plans_dir, sanitize_filename, ensure_directories

    print_banner("team-debate")
    print(f"Topic: {topic[:100]}...")
    if focus:
        print(f"Focus: {focus}")
    print()

    orchestrator = DiamondOrchestrator()

    # Execute sequential 4-step debate
    result = orchestrator.execute_diamond_debate(
        topic=topic,
        focus=focus if focus else None,
        context=context
    )

    # Ensure build plans directory exists
    ensure_directories()

    # Display results in format matching PowerShell script
    print(f"\n{'='*60}")
    print("TEAM DEBATE RESULTS")
    print(f"{'='*60}\n")

    # Step 1: Architect
    print("1️⃣  Step 1: Architect (gemini-architect)")
    print(f"   Time: {result.step1_architect.latency_seconds:.2f}s | Cost: ${result.step1_architect.cost:.4f}")
    if result.step1_architect.success:
        preview = result.step1_architect.content[:300].replace('\n', ' ')
        print(f"\n   {preview}...")
    else:
        print(f"\n   ✗ Error: {result.step1_architect.error}")

    # Step 2: Auditor
    print(f"\n2️⃣  Step 2: Auditor (deepseek-v3)")
    print(f"   Time: {result.step2_auditor.latency_seconds:.2f}s | Cost: ${result.step2_auditor.cost:.4f}")
    if result.step2_auditor.success:
        preview = result.step2_auditor.content[:300].replace('\n', ' ')
        print(f"\n   {preview}...")
    else:
        print(f"\n   ✗ Error: {result.step2_auditor.error}")

    # Step 3: Contextualist
    print(f"\n3️⃣  Step 3: Contextualist (kimi-researcher)")
    print(f"   Time: {result.step3_contextualist.latency_seconds:.2f}s | Cost: ${result.step3_contextualist.cost:.4f}")
    if result.step3_contextualist.success:
        preview = result.step3_contextualist.content[:300].replace('\n', ' ')
        print(f"\n   {preview}...")
    else:
        print(f"\n   ✗ Error: {result.step3_contextualist.error}")

    # Step 4: Judge
    print(f"\n4️⃣  Step 4: Judge (opus-synthesis)")
    print(f"   Time: {result.step4_judge.latency_seconds:.2f}s | Cost: ${result.step4_judge.cost:.4f}")
    if result.step4_judge.success:
        print(f"\n{'─'*60}")
        print("🏛️  FINAL COUNCIL DECREE")
        print(f"{'─'*60}")
        print(result.step4_judge.content)
    else:
        print(f"\n   ✗ Error: {result.step4_judge.error}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(result.format_summary())

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = sanitize_filename(topic.lower().replace(" ", "-")[:40])
    focus_suffix = f"-{focus}" if focus else ""
    filename = f"{timestamp}{focus_suffix}-{slug}.md"
    artifact_path = get_build_plans_dir() / filename

    # Format as markdown
    markdown = format_team_debate_markdown(topic, focus, context, result)

    try:
        artifact_path.write_text(markdown, encoding="utf-8")
        print(f"\n✓ Council decree saved to: {artifact_path.name}")
    except Exception as e:
        print(f"\n⚠ Warning: Could not save artifact: {e}", file=sys.stderr)

    return 0


def format_team_debate_markdown(topic: str, focus: str, context: str, result) -> str:
    """Format team debate results as markdown artifact."""
    from datetime import datetime

    md = f"""# Council Review: {topic}

**Generated:** {datetime.now().isoformat()}
**Mode:** Team Debate (Sequential 4-Step)
**Focus:** {focus if focus else "None"}
**Total Time:** {result.total_latency:.2f}s
**Total Cost:** ${result.total_cost:.4f}
**Total Tokens:** {result.total_tokens}

---

## 🏛️ FINAL COUNCIL DECREE

{result.step4_judge.content if result.step4_judge.success else "Error: " + result.step4_judge.error}

---

## Full Debate Transcripts

### Step 1: Architect (gemini-architect)
**Time:** {result.step1_architect.latency_seconds:.2f}s | **Cost:** ${result.step1_architect.cost:.4f} | **Tokens:** {result.step1_architect.tokens_used}

{result.step1_architect.content if result.step1_architect.success else "Error: " + result.step1_architect.error}

---

### Step 2: Auditor (deepseek-v3)
**Time:** {result.step2_auditor.latency_seconds:.2f}s | **Cost:** ${result.step2_auditor.cost:.4f} | **Tokens:** {result.step2_auditor.tokens_used}

{result.step2_auditor.content if result.step2_auditor.success else "Error: " + result.step2_auditor.error}

---

### Step 3: Contextualist (kimi-researcher)
**Time:** {result.step3_contextualist.latency_seconds:.2f}s | **Cost:** ${result.step3_contextualist.cost:.4f} | **Tokens:** {result.step3_contextualist.tokens_used}

{result.step3_contextualist.content if result.step3_contextualist.success else "Error: " + result.step3_contextualist.error}

---

### Step 4: Judge (opus-synthesis)
**Time:** {result.step4_judge.latency_seconds:.2f}s | **Cost:** ${result.step4_judge.cost:.4f} | **Tokens:** {result.step4_judge.tokens_used}

{result.step4_judge.content if result.step4_judge.success else "Error: " + result.step4_judge.error}

---

*Generated by Council Team Debate Mode*
*Architecture v2.1 - Multi-Tiered AI Collaboration System*
"""
    return md


def main():
    """Main entry point for Council skill."""
    if len(sys.argv) < 3:
        print("Council Multi-Tiered AI Collaboration System")
        print("\nUsage:")
        print("  python skill.py brainstorm <prompt>")
        print("  python skill.py refine <input>")
        print("  python skill.py build-plan <topic>")
        print("  python skill.py build-review <summary>")
        print("  python skill.py opus-gatekeeper <query>")
        print("  python skill.py diamond-debate <topic>")
        print("  python skill.py team-debate <topic>")
        print("\nExamples:")
        print("  python skill.py brainstorm Ways to improve API performance")
        print("  python skill.py refine Create a web scraper with caching")
        print("  python skill.py build-plan Build a Markdown caching system")
        print("  python skill.py build-review Created scraper with UTF-8 support")
        print("  python skill.py opus-gatekeeper Design a new auth system")
        print("  python skill.py diamond-debate Should we use PostgreSQL or MongoDB?")
        print("  python skill.py team-debate Design a new authentication system")
        sys.exit(1)

    mode = sys.argv[1].lower()
    prompt = " ".join(sys.argv[2:])

    # Mode routing
    modes = {
        "brainstorm": mode_brainstorm,
        "refine": mode_refine,
        "build-plan": mode_build_plan,
        "build-review": mode_build_review,
        "opus-gatekeeper": mode_opus_gatekeeper,
        "diamond-debate": mode_diamond_debate,
        "team-debate": mode_team_debate
    }

    handler = modes.get(mode)
    if not handler:
        print(f"Error: Unknown mode '{mode}'", file=sys.stderr)
        print(f"Available modes: {', '.join(modes.keys())}", file=sys.stderr)
        sys.exit(1)

    # Execute mode
    sys.exit(handler(prompt))


if __name__ == "__main__":
    # UTF-8 output for Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    main()
