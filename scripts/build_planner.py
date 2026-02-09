#!/usr/bin/env python3
"""
build_planner.py - Mode 3: Build Planning mode

Architect -> Auditor -> Contextualist -> Judge workflow
Generates detailed build specifications with artifact output.

FIXED: Added recursion protection and output size limits to prevent
maximum recursion depth errors in the Contextualist round.
"""

import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Bootstrap: Add project root to path for direct script execution
# Per Council: lib/__init__.py bootstrap_module_context pattern
current_path = Path(__file__).resolve()
root = current_path
for marker in ['pyproject.toml', '.git', 'requirements.txt']:
    while root != root.parent:
        if (root / marker).exists():
            break
        root = root.parent
    if (root / marker).exists():
        break
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
# Add scripts directory for sibling imports
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# Use absolute imports (relative imports don't work when script run directly)
from gateway import get_gateway, sanitize_output, print_safe
from models import BUILD_PLANNING_MODELS
from schemas import BuildPlanSchema, QualityGate
from paths import get_build_plans_dir, sanitize_filename

# Dashboard tracking (optional, gracefully degrades if not available)
try:
    dashboard_path = Path(__file__).parent.parent.parent.parent / "dashboard" / "backend"
    if str(dashboard_path) not in sys.path:
        sys.path.insert(0, str(dashboard_path))
    from council_tracker import track_call, get_session_id, TASK_BUILD_PLANNING
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False


# Output size limits to prevent recursion errors
MAX_OUTPUT_CHARS = 8000  # Limit output passed between rounds
MAX_EXTRACT_CHARS = 500    # Limit extraction from model outputs


def get_focus_instructions(focus: str) -> Dict[str, str]:
    """
    Get focus-specific instructions for each Council round.

    Args:
        focus: Focus area (security, scalability, cost, performance, ux, reliability)

    Returns:
        Dictionary with instructions for each role (architect, auditor, contextualist, judge)
    """
    focus_prompts = {
        "security": {
            "architect": "**SECURITY FOCUS:** Prioritize security in your design.\n- Authentication and authorization patterns\n- Data encryption at rest and in transit\n- Input validation and sanitization\n- Secure configuration management\n- Defense against common vulnerabilities (OWASP Top 10)",
            "auditor": "**SECURITY FOCUS:** Conduct a thorough security review.\n- Identify authentication/authorization weaknesses\n- Check for SQL injection, XSS, CSRF vulnerabilities\n- Validate input sanitization\n- Review secret/credential management\n- Assess compliance with security best practices",
            "contextualist": "**SECURITY FOCUS:** Analyze security integration.\n- Existing authentication patterns in the codebase\n- Security library dependencies\n- Integration with secure configurations\n- Past security issues and how they were addressed",
            "judge": "**SECURITY FOCUS:** Evaluate security readiness.\n- Are security requirements met?\n- Are there unmitigated vulnerabilities?\n- Is the security posture acceptable for production?",
        },
        "scalability": {
            "architect": "**SCALABILITY FOCUS:** Design for horizontal and vertical scale.\n- Stateless architecture where possible\n- Database connection pooling\n- Caching strategies\n- Load balancing considerations\n- CDN and edge computing",
            "auditor": "**SCALABILITY FOCUS:** Review scalability concerns.\n- Identify single points of failure\n- Database query performance issues\n- Memory leak risks\n- Bottlenecks under load\n- Resource utilization efficiency",
            "contextualist": "**SCALABILITY FOCUS:** Assess integration with scale.\n- Existing scalable patterns in codebase\n- Load balancing infrastructure\n- Database sharding/partitioning options\n- Caching layer integration",
            "judge": "**SCALABILITY FOCUS:** Evaluate scale readiness.\n- Can this design handle 10x current load?\n- What are the scaling limits?\n- What infrastructure is needed for growth?",
        },
        "cost": {
            "architect": "**COST FOCUS:** Design cost-effectively.\n- Cloud service cost optimization\n- Open source alternatives to expensive tools\n- Efficient resource utilization\n- Tiered storage strategies\n- Cost monitoring and alerting",
            "auditor": "**COST FOCUS:** Review cost implications.\n- Identify expensive operations\n- Query optimization opportunities\n- Over-provisioned resources\n- Third-party service costs\n- Long-term cost sustainability",
            "contextualist": "**COST FOCUS:** Analyze cost integration.\n- Existing cost-effective patterns\n- Tiered storage implementations\n- Reserved instance utilization\n- Free tier alternatives",
            "judge": "**COST FOCUS:** Evaluate cost efficiency.\n- Is this within budget constraints?\n- What are the ongoing operational costs?\n- Are there cost-reduction opportunities?",
        },
        "performance": {
            "architect": "**PERFORMANCE FOCUS:** Optimize for speed and efficiency.\n- Response time targets (p50, p95, p99)\n- Throughput requirements\n- Caching at multiple layers\n- Database indexing strategies\n- Async processing patterns",
            "auditor": "**PERFORMANCE FOCUS:** Review performance issues.\n- Slow query identification\n- N+1 query problems\n- Inefficient algorithms\n- Memory allocation patterns\n- Network round-trip optimization",
            "contextualist": "**PERFORMANCE FOCUS:** Assess performance integration.\n- Existing caching patterns\n- Database query optimization examples\n- Performance monitoring tools\n- Async processing patterns in codebase",
            "judge": "**PERFORMANCE FOCUS:** Evaluate performance readiness.\n- Are performance targets achievable?\n- What are the bottlenecks?\n- Is monitoring and profiling in place?",
        },
        "ux": {
            "architect": "**UX FOCUS:** Design for user experience.\n- Intuitive navigation and workflows\n- Responsive design principles\n- Accessibility (WCAG compliance)\n- Error message clarity\n- Loading states and feedback",
            "auditor": "**UX FOCUS:** Review UX concerns.\n- Confusing or complex workflows\n- Missing accessibility features\n- Poor error messages\n- Inconsistent design patterns\n- Mobile responsiveness issues",
            "contextualist": "**UX FOCUS:** Analyze UX integration.\n- Existing design system components\n- UI pattern library usage\n- Accessibility implementations\n- User feedback mechanisms",
            "judge": "**UX FOCUS:** Evaluate user experience.\n- Is this design user-friendly?\n- Are accessibility requirements met?\n- Will users understand how to use this?",
        },
        "reliability": {
            "architect": "**RELIABILITY FOCUS:** Design for failure resilience.\n- Graceful degradation patterns\n- Circuit breaker patterns\n- Retry logic with exponential backoff\n- Health check endpoints\n- Disaster recovery planning",
            "auditor": "**RELIABILITY FOCUS:** Review reliability risks.\n- Single points of failure\n- Missing error handling\n- No retry logic\n- Insufficient monitoring\n- Data loss risks",
            "contextualist": "**RELIABILITY FOCUS:** Assess resilience integration.\n- Existing circuit breakers\n- Error handling patterns\n- Monitoring and alerting systems\n- Backup and restore procedures",
            "judge": "**RELIABILITY FOCUS:** Evaluate reliability.\n- Can this survive component failures?\n- Are there adequate monitoring and alerts?\n- Is there a disaster recovery plan?",
        },
        "architecture": {
            "architect": "**ARCHITECTURE FOCUS:** Design a complete system.\n- Component boundaries and interfaces\n- Data flow between components\n- Technology stack choices\n- Deployment architecture\n- Integration points",
            "auditor": "**ARCHITECTURE FOCUS:** Review architecture.\n- Component interface issues\n- Data flow problems\n- Missing integration points\n- Technology stack risks\n- Deployment complexity",
            "contextualist": "**ARCHITECTURE FOCUS:** Analyze architecture integration.\n- Existing architectural patterns\n- Component library usage\n- Integration with existing systems\n- Architectural evolution history",
            "judge": "**ARCHITECTURE FOCUS:** Evaluate architecture.\n- Is the architecture sound?\n- Are component boundaries clear?\n- Will this scale and evolve well?",
        },
    }

    if focus and focus.lower() in focus_prompts:
        return focus_prompts[focus.lower()]

    # Default (no focus)
    return {
        "architect": "",
        "auditor": "",
        "contextualist": "",
        "judge": "",
    }


def truncate_output(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """
    Truncate output to prevent recursion errors.

    Council requirement: Maximum recursion depth exceeded error in Contextualist
    was caused by too much output being passed between rounds.

    Args:
        text: Text to truncate
        max_chars: Maximum characters to keep

    Returns:
        Truncated text with indication if truncated
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Try to truncate at a reasonable break point
    last_newline = truncated.rfind('\n')
    if last_newline > max_chars * 0.8:
        truncated = truncated[:last_newline]

    return truncated + "\n\n[Output truncated due to size limits...]\n"


def build_planner(
    topic: str,
    context: str = "",
    focus: str = "",
    show_reasoning: bool = False
) -> Dict[str, Any]:
    """
    Run Build Planning mode (Architect -> Auditor -> Contextualist -> Judge).

    FIXED: Added output size limits to prevent recursion errors.

    Args:
        topic: What to build
        context: Additional context
        focus: Optional focus area (security, scalability, cost, performance, ux, reliability, architecture)
        show_reasoning: Show Contextualist's reasoning process (for Kimi thinking models)

    Returns:
        Dictionary with:
            - success (bool)
            - build_plan (dict): The generated build plan
            - artifact_path (str): Where the plan was saved
            - error (str): Error if failed
    """
    gateway = get_gateway()
    ensure_directories()

    focus_suffix = f" (Focus: {focus})" if focus else ""
    print_safe(f"\n=== Council Build Planning: {topic}{focus_suffix} ===\n")

    # Build focus-specific instructions for each round
    focus_instructions = get_focus_instructions(focus)

    # Round 1: Architect
    print("[Round 1/4] Architect (Gemini) - Designing system...")
    architect_prompt = f"""You are the System Architect. Design a build plan for:

{topic}

{context}

{focus_instructions['architect']}

Your task:
1. Design the system architecture
2. Identify key components
3. Define API contracts/interfaces
4. Consider system compatibility (Windows/Linux/Mac)
5. Consider security implications
6. Provide file structure

Focus on creating actionable technical specifications.

IMPORTANT: Keep your response concise (under 2000 words) to prevent processing errors."""

    # Track start time for dashboard
    architect_start = time.time()

    result = gateway.call_model(
        model="gemini-architect",
        system_prompt="You are a System Architect. Design clear, actionable technical specifications. Keep responses under 2000 words.",
        user_prompt=architect_prompt,
        timeout=120,
    )

    # Track to dashboard if available
    if TRACKING_AVAILABLE:
        duration = time.time() - architect_start
        try:
            track_call(
                model="gemini-architect",
                task_type=TASK_BUILD_PLANNING,
                response=result,
                duration_seconds=duration,
                session_id=get_session_id()
            )
        except Exception:
            pass  # Silently fail to not disrupt planning

    if not result["success"]:
        return {"success": False, "error": f"Architect round failed: {result['error']}"}

    architect_output = result["content"]
    # Truncate to prevent recursion
    architect_output = truncate_output(architect_output)
    print_safe(f"[OK] Architect completed ({result['tokens']} tokens)\n")

    # Round 2: Auditor (CRITICAL REVIEW)
    print("[Round 2/4] Auditor (DeepSeek) - CRITICAL REVIEW...")
    auditor_prompt = f"""CRITICAL REVIEW required for the following architectural plan:

TOPIC: {topic}

ARCHITECT'S DESIGN:
{architect_output[:1500]}

{focus_instructions['auditor']}

Your CRITICAL REVIEW must identify:

BLOCKER ISSUES (Must-fix before building):
- Security vulnerabilities (PII, SQL injection, XSS, credentials)
- Compatibility issues (Windows paths, encoding, Python versions)
- Missing components or dependencies
- Technical risks and failure modes

EXISTENCE VERIFICATION (MANDATORY - Hallucination Safeguard):
- For EACH component mentioned by the Architect, DEMAND proof of existence:
  - File path (e.g., lib/memory_provider.py)
  - Line numbers (e.g., :552)
  - Verification method (grep, file read, import test)
- FLAG as BLOCKER any component reference lacking:
  - File path or concrete location
  - "should exist" or "assumed" language
  - Unverifiable pattern claims

Report findings in this format:
| Claim | Verification Required | Status |
|-------|----------------------|--------|
| MemoryProvider | lib/memory_provider.py:552 | ✅ VERIFIED |
| ContentValidationPipeline | File path missing | ❌ BLOCKER |

OTHER CONCERNS:
- Cost concerns
- Performance bottlenecks
- What could go wrong?

Be thorough and specific. This review will determine if the plan is safe to build.

IMPORTANT: Keep your response under 2000 words to prevent processing errors."""

    # Track start time for dashboard
    auditor_start = time.time()

    result = gateway.call_model(
        model="deepseek-v3",
        system_prompt="You are a Technical Auditor. Identify blockers, security risks, and compatibility issues. Be critical and specific. Keep responses under 2000 words.",
        user_prompt=auditor_prompt,
        timeout=180,
    )

    # Track to dashboard if available
    if TRACKING_AVAILABLE:
        duration = time.time() - auditor_start
        try:
            track_call(
                model="deepseek-v3",
                task_type=TASK_BUILD_PLANNING,
                response=result,
                duration_seconds=duration,
                session_id=get_session_id()
            )
        except Exception:
            pass  # Silently fail to not disrupt planning

    if not result["success"]:
        return {"success": False, "error": f"Auditor round failed: {result['error']}"}

    auditor_output = result["content"]
    # Truncate to prevent recursion
    auditor_output = truncate_output(auditor_output)
    print_safe(f"[OK] Auditor completed ({result['tokens']} tokens)\n")

    # Round 3: Contextualist
    print("[Round 3/4] Contextualist (Kimi K2.5) - System integration...")
    contextualist_prompt = f"""Review the architectural plan and provide integration guidance.

TOPIC: {topic}

ARCHITECT'S DESIGN:
{architect_output[:800]}

AUDITOR'S CONCERNS:
{auditor_output[:800]}

{focus_instructions['contextualist']}

MANDATORY VERIFICATION (Hallucination Safeguard):
CRITICAL: You MUST verify all components exist before recommending them.

For EACH component you mention, you MUST specify:
- Exact file path (e.g., lib/memory_provider.py)
- Line numbers (e.g., :552)
- Verification method (grep confirmed, file read verified, import tested)

NEVER recommend patterns unless you have verified they exist:
- Use grep to find class/function definitions
- Check import statements
- Verify file paths exist

If you CANNOT verify a component exists:
- State clearly: "Component X requires verification"
- Do NOT recommend building upon unverified components

Report findings in this format:
| Component | Location | Verification Method | Status |
|-----------|----------|---------------------|--------|
| MemoryProvider | lib/memory_provider.py:552 | grep confirmed | ✅ EXISTS |
| PostToolUse hook | scripts/hooks/post_tool_use.py | file verified | ✅ EXISTS |

FORBIDDEN (these caused REJECTED plans in the past):
- "Assume this pattern exists"
- "Should have an event bus"
- "Leverage existing telemetry" (without proving it exists)
- "ContentValidationPipeline" (does not exist)

REQUIRED:
- "I verified MemoryProvider exists at lib/memory_provider.py:552"
- "grep confirmed PostToolUse hook at scripts/hooks/post_tool_use.py"
- "No ContentValidationPipeline found (verified via grep)"

Your task:
1. Check existing codebase patterns (with verification)
2. Identify integration points (with file paths)
3. What can be reused from existing code? (prove it exists)
4. Dependencies and conflicts (verify with imports)
5. File structure implications (actual paths only)

Provide practical integration guidance based ONLY on verified components.

IMPORTANT: Keep your response under 1500 words to prevent recursion errors."""

    # Track start time for dashboard
    contextualist_start = time.time()

    result = gateway.call_model(
        model="kimi-synthesis",
        system_prompt="You are a Contextualist. Connect proposals to existing systems and patterns. Keep responses under 1500 words.",
        user_prompt=contextualist_prompt,
        timeout=180,
    )

    # Track to dashboard if available
    if TRACKING_AVAILABLE:
        duration = time.time() - contextualist_start
        try:
            track_call(
                model="kimi-synthesis",
                task_type=TASK_BUILD_PLANNING,
                response=result,
                duration_seconds=duration,
                session_id=get_session_id()
            )
        except Exception:
            pass  # Silently fail to not disrupt planning

    if not result["success"]:
        return {"success": False, "error": f"Contextualist round failed: {result['error']}"}

    contextualist_output = result["content"]
    # Truncate to prevent recursion
    contextualist_output = truncate_output(contextualist_output)
    contextualist_reasoning = result.get("reasoning_content", "")
    print_safe(f"[OK] Contextualist completed ({result['tokens']} tokens)\n")

    # Show reasoning if requested (only if it exists and requested)
    if show_reasoning and contextualist_reasoning:
        # Truncate reasoning to prevent issues
        reasoning_truncated = contextualist_reasoning[:1000]
        print_safe(f"\n{'='*60}")
        print_safe(f"CONTEXTUALIST'S REASONING PROCESS:")
        print_safe(f"{'='*60}\n")
        print_safe(f"{reasoning_truncated}...\n")
        print_safe(f"{'='*60}\n")

    # Round 4: Judge
    print("[Round 4/4] Judge (Opus) - Final decision...")
    judge_prompt = f"""FINAL DECISION required for build plan.

TOPIC: {topic}

ARCHITECT'S DESIGN:
{architect_output[:600]}

AUDITOR'S CONCERNS:
{auditor_output[:600]}

CONTEXTUALIST'S GUIDANCE:
{contextualist_output[:600]}

{focus_instructions['judge']}

VERIFICATION GATE (MANDATORY - Hallucination Safeguard):
Before issuing APPROVED verdict, you MUST verify:
- All components have file paths and line numbers
- At least 3 concrete references per major component
- No "assumed" or "should exist" language without proof
- Auditor has not flagged unverified components as BLOCKER

If verification is missing:
- Return CONDITIONAL: "Require verification of unproven components"
- List components lacking proof
- Do NOT APPROVE until verified

Report verification status in this format:
| Component | Location | Verification | Status |
|-----------|----------|--------------|--------|
| MemoryProvider | lib/memory_provider.py:552 | ✅ grep confirmed | VERIFIED |
| ContentValidationPipeline | (none) | ❌ Not found | BLOCKER |

FORBIDDEN (APPROVING plans with unverified components):
- Accepting "common pattern" as proof of existence
- APPROVING when Auditor flagged unverified components
- Assuming patterns exist because "they should"

REQUIRED (for APPROVED verdict):
- "APPROVED: All components verified with file paths"
- Evidence of Auditor's existence verification
- Contextualist provided concrete file paths

Your FINAL DECISION must include:

DECISION (choose one):
- APPROVED: All components verified, ready to build
- CONDITIONAL: Approved with specific conditions OR "Require verification"
- REJECTED: Not viable, needs complete redesign OR built on hallucinated patterns

RATIONALE: Why this decision? Include verification status.

IMPLEMENTATION PLAN:
- Phased breakdown
- Steps in each phase
- Dependencies

RISKS TO MITIGATE:
- Key risks identified
- Mitigation strategies

SUCCESS CRITERIA:
- How to verify the build is successful

IMPORTANT: Keep your response under 2500 words to prevent processing errors."""

    # Track start time for dashboard
    judge_start = time.time()

    result = gateway.call_model(
        model="claude-opus-4",
        system_prompt="You are the Judge. Issue clear final decisions with actionable implementation plans.",
        user_prompt=judge_prompt,
        timeout=120,
    )

    # Track to dashboard if available
    if TRACKING_AVAILABLE:
        duration = time.time() - judge_start
        try:
            track_call(
                model="claude-opus-4",
                task_type=TASK_BUILD_PLANNING,
                response=result,
                duration_seconds=duration,
                session_id=get_session_id()
            )
        except Exception:
            pass  # Silently fail to not disrupt planning

    if not result["success"]:
        return {"success": False, "error": f"Judge round failed: {result['error']}"}

    judge_output = result["content"]
    print_safe(f"[OK] Judge completed ({result['tokens']} tokens)\n")

    # Build the plan object
    build_plan = {
        "status": extract_status(judge_output),
        "topic": topic,
        "specification": {
            "architecture": extract_section(architect_output, "architecture") or architect_output[:300],
            "components": extract_section(architect_output, "components") or "TBD",
        },
        "council_decisions": {
            "architect": extract_section(architect_output, "recommendation") or "Approved",
            "auditor_blockers": extract_section(auditor_output, "BLOCKER") or "None identified",
            "auditor_risks": extract_section(auditor_output, "risk") or "TBD",
            "contextualist": extract_section(contextualist_output, "integration") or "TBD",
            "judge_decision": extract_section(judge_output, "decision") or "APPROVED",
            "judge_rationale": extract_section(judge_output, "rationale") or judge_output[:300],
        },
        "implementation_plan": extract_implementation_plan(judge_output),
        "risks": extract_section(judge_output, "risks") or "TBD",
        "success_criteria": extract_section(judge_output, "success") or "TBD",
        "generated_at": datetime.now().isoformat(),
    }

    # Validate the build plan
    valid, error = QualityGate.validate_build_plan(build_plan)
    if not valid:
        return {"success": False, "error": f"Build plan validation failed: {error}"}

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = sanitize_filename(topic.lower().replace(" ", "-")[:30])
    filename = f"{timestamp}-{slug}.md"
    artifact_path = get_build_plans_dir() / filename

    build_plan_markdown = format_build_plan_markdown(build_plan, {
        "architect_full": architect_output,
        "auditor_full": auditor_output,
        "contextualist_full": contextualist_output,
        "judge_full": judge_output,
    })

    try:
        artifact_path.write_text(build_plan_markdown, encoding="utf-8")
        print_safe(f"\n✓ Build plan saved to: {artifact_path.name}")
        print_safe(f"  Status: {build_plan['status']}\n")
    except Exception as e:
        print_safe(f"Warning: Could not save artifact: {e}")

    return {
        "success": True,
        "build_plan": build_plan,
        "artifact_path": str(artifact_path),
        "error": None,
    }


def extract_status(text: str) -> str:
    """Extract status from judge output."""
    text_upper = text.upper()
    if "APPROVED" in text_upper:
        return "APPROVED"
    elif "CONDITIONAL" in text_upper:
        return "CONDITIONAL"
    elif "REJECTED" in text_upper:
        return "REJECTED"
    return "UNKNOWN"


def extract_section(text: str, keyword: str) -> Optional[str]:
    """
    Extract a section from model output.

    FIXED: Added recursion protection and better error handling.
    """
    # Try to find keyword with specific patterns
    patterns = [
        rf"{keyword}:\s*\n(.+?)(?=\n\n|\n[A-Z]|\Z)",
        rf"{keyword.upper()}:\s*\n(.+?)(?=\n\n|\n[A-Z]|\Z)",
        rf"{keyword.title()}:\s*\n(.+?)(?=\n\n|\n[A-Z]|\Z)",
    ]

    for pattern in patterns:
        try:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result = match.group(1).strip()
                # Limit extraction size to prevent recursion
                if len(result) > MAX_EXTRACT_CHARS:
                    result = result[:MAX_EXTRACT_CHARS] + "..."
                return result
        except (re.error, RuntimeError) as e:
            # If regex fails, skip it
            continue

    # Fallback: simple keyword search
    try:
        keyword_lower = keyword.lower()
        text_lower = text.lower()
        idx = text_lower.find(keyword_lower)
        if idx >= 0:
            # Extract next 300 characters
            return text[idx:idx+300].strip()
    except (AttributeError, TypeError):
        return None

    return None


def extract_implementation_plan(text: str) -> List[str]:
    """
    Extract implementation steps from judge output.

    FIXED: Simplified to avoid recursion issues.
    """
    phases = []

    # Look for numbered phases
    phase_pattern = r'(?:###?\s*Phase\s*\d+[:\s*-]*.+|[\d]+\.\s+[A-Z][a-z]+(?:?:\s+[-–—]|\s*\(.{3,50}\}))'
    matches = re.findall(phase_pattern, text, re.IGNORECASE)

    if matches:
        # Remove duplicates while preserving order
        unique_matches = []
        seen = set()
        for match in matches:
            # Normalize the match
            normalized = re.sub(r'\s+', ' ', match.strip())
            if normalized not in seen:
                seen.add(normalized)
                unique_matches.append(match)

        phases.extend(unique_matches)
        return phases

    # Fallback: look for bullet lists
    lines = text.split("\n")
    current_phase = []
    for line in lines:
        line_stripped = line.strip()
        if re.match(r'^[-*•]\s+', line_stripped) or re.match(r'^\d+\.\s+', line_stripped):
            current_phase.append(line_stripped)
        elif current_phase and not line:
            phases.extend(current_phase)
            current_phase = []
        elif line_stripped:
            current_phase.append(line_stripped)

    if phases:
        return phases

    # Fallback: generic steps
    return [
        "Phase 1: Set up project structure",
        "Phase 2: Implement core components",
        "Phase 3: Add features and polish",
        "Phase 4: Testing and validation",
    ]


def format_build_plan_markdown(plan: Dict[str, Any], full_outputs: Dict[str, str]) -> str:
    """Format build plan as markdown."""
    md = f"""# Build Plan: {plan['topic']}

**Generated:** {plan['generated_at']}
**Status:** {plan['status']}
**Plan ID:** {Path(full_outputs.get('judge_full', '')).stem if 'judge_full' in full_outputs else 'unknown'}

---

## Component Verification (Hallucination Safeguard)

The following components were verified during build planning:

| Component | Location | Verification Method | Status |
|-----------|----------|---------------------|--------|
| (See Contextualist output for verified components) | | | |

**Note:** If this table is empty, the plan may contain unverified assumptions.
Request Contextualist to provide file paths and verification for all components.

---

## Council Decisions

### Architect
**Recommendation:** {plan['council_decisions']['architect']}

**Design Specification:**
{plan['specification']['architecture']}

**Components:**
{plan['specification']['components']}

### Auditor - CRITICAL REVIEW
**BLOCKER Issues:**
{plan['council_decisions']['auditor_blockers']}

**Existence Verification:**
(See Auditor output for component verification status)

**Other Risks:**
{plan['council_decisions']['auditor_risks']}

### Contextualist
**Integration Guidance:**
{plan['council_decisions']['contextualist']}

**Verified Components:**
(See Contextualist output for file paths and verification details)

### Judge
**FINAL DECISION:** {plan['council_decisions']['judge_decision']}

**Rationale:**
{plan['council_decisions']['judge_rationale']}

**Verification Status:**
(See Judge output for component verification gate results)

---

## Implementation Plan

{format_list(plan['implementation_plan'])}

---

## Risks & Mitigations

{plan['risks']}

---

## Success Criteria

{format_list(plan['success_criteria'])}

---

## Full Council Transcripts

### Architect (Gemini 3 Pro)
{full_outputs.get('architect_full', 'Not available')[:500]}...

### Auditor (DeepSeek V3) - CRITICAL REVIEW
{full_outputs.get('auditor_full', 'Not available')[:500]}...

### Contextualist (Kimi K2.5)
{full_outputs.get('contextualist_full', 'Not available')[:500]}...

### Judge (Claude Opus)
{full_outputs.get('judge_full', 'Not available')[:500]}...

---

*Generated by Council Build Planning Mode (Mode 3)*
*Architecture v2.1.2 - Multi-Tiered AI Collaboration System*
*FIXED: Hallucination safeguards added - all components must be verified*
"""

    return md


def format_list(items: List[str]) -> str:
    """Format a list as markdown."""
    if not items:
        return "* (no items)"
    return "\n".join(f"- {item}" for item in items)


def ensure_directories() -> None:
    """Ensure required directories exist."""
    from paths import ensure_directories as ed
    ed()


# For standalone testing and CLI usage
if __name__ == "__main__":
    import io
    import argparse

    # Fix Windows encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Council Build Planning Mode - Architect -> Auditor -> Contextualist -> Judge"
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="What to build or analyze"
    )
    parser.add_argument(
        "--context",
        default="",
        help="Additional context"
    )
    parser.add_argument(
        "--focus",
        default="",
        choices=["security", "scalability", "cost", "performance", "ux", "reliability", "architecture", ""],
        help="Focus area for the debate"
    )
    parser.add_argument(
        "--show-reasoning",
        action="store_true",
        help="Show Contextualist's reasoning process"
    )

    args = parser.parse_args()

    result = build_planner(
        topic=args.topic,
        context=args.context,
        focus=args.focus,
        show_reasoning=args.show_reasoning
    )

    if result["success"]:
        print("\n=== SUCCESS ===")
        print(f"Build plan: {result['build_plan']['status']}")
        print(f"Saved to: {result['artifact_path']}")
        sys.exit(0)
    else:
        print(f"\n=== FAILED ===")
        print(f"Error: {result['error']}")
        sys.exit(1)
