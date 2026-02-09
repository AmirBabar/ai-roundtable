#!/usr/bin/env python3
"""
build_reviewer.py - Post-Build Review Mode

Reviews completed builds against build plan criteria.
Validates implementation success and identifies issues.
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
from paths import get_build_plans_dir, sanitize_filename

# Dashboard tracking (optional, gracefully degrades if not available)
try:
    dashboard_path = Path(__file__).parent.parent.parent.parent / "dashboard" / "backend"
    if str(dashboard_path) not in sys.path:
        sys.path.insert(0, str(dashboard_path))
    from council_tracker import track_call, get_session_id
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False


def review_build(
    build_plan_path: Optional[str] = None,
    implementation_summary: str = "",
    files_changed: Optional[List[str]] = None,
    manual_review_criteria: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Review a completed build against its plan criteria.

    Args:
        build_plan_path: Path to build plan markdown file (optional)
        implementation_summary: What was actually implemented
        files_changed: List of files that were modified/created
        manual_review_criteria: Custom criteria if no build plan exists

    Returns:
        Dictionary with:
            - success (bool)
            - review_report (dict): Detailed review findings
            - passed_checks (list): Criteria that passed
            - failed_checks (list): Criteria that failed
            - warnings (list): Concerns that don't block deployment
            - recommendation (str): APPROVED/CONDITIONAL/REJECTED
            - error (str): Error if failed
    """
    gateway = get_gateway()

    print_safe(f"\n=== Council Build Reviewer ===")
    print_safe(f"Reviewing implementation...\n")

    # Load build plan if provided
    build_plan = None
    if build_plan_path:
        plan_path = Path(build_plan_path)
        if not plan_path.is_absolute():
            # Try relative to build plans directory
            plan_path = get_build_plans_dir() / Path(build_plan_path)

        if plan_path.exists():
            build_plan = parse_build_plan(plan_path)
            print_safe(f"Loaded build plan: {plan_path.name}")
        else:
            print_safe(f"Build plan not found: {build_plan_path}")
            print_safe(f"Proceeding with manual criteria...\n")

    # Build review prompt
    review_prompt = build_review_prompt(
        build_plan,
        implementation_summary,
        files_changed or [],
        manual_review_criteria
    )

    # Use DeepSeek V3 for thorough review (good balance of speed and depth)
    review_start = time.time()

    result = gateway.call_model(
        model="deepseek-v3",
        system_prompt="""You are a Build Reviewer. Your task is to thoroughly validate that an implementation matches its specification.

Be thorough but fair. Distinguish between:
- BLOCKER issues that must be fixed before deployment
- WARNINGS that should be addressed but don't block
- PASS items that meet requirements

Format your response as:
VERDICT: [APPROVED / CONDITIONAL / REJECTED]

CRITERIA REVIEW:
[Pass/Fail/Warning] - [Criteria name]
- [Specific feedback]

RECOMMENDATIONS:
[Actionable suggestions for any issues]""",        user_prompt=review_prompt,
        timeout=120,
    )

    # Track to dashboard if available
    if TRACKING_AVAILABLE:
        duration = time.time() - review_start
        try:
            track_call(
                model="deepseek-v3",
                task_type="build-reviewer",
                response=result,
                duration_seconds=duration,
                session_id=get_session_id()
            )
        except Exception:
            pass  # Silently fail to not disrupt review

    if not result["success"]:
        return {
            "success": False,
            "error": f"Review failed: {result['error']}",
        }

    review_output = result["content"]
    print_safe(f"\n[OK] Review complete ({result['tokens']} tokens)")

    # Parse the review output
    review_report = parse_review_output(review_output, build_plan)

    print_safe(f"\n✓ Review complete")
    print_safe(f"  Verdict: {review_report['recommendation']}")
    print_safe(f"  Passed: {len(review_report['passed_checks'])}")
    print_safe(f"  Failed: {len(review_report['failed_checks'])}")
    print_safe(f"  Warnings: {len(review_report['warnings'])}\n")

    return {
        "success": True,
        "review_report": review_report,
        "passed_checks": review_report["passed_checks"],
        "failed_checks": review_report["failed_checks"],
        "warnings": review_report["warnings"],
        "recommendation": review_report["recommendation"],
        "full_review": review_output,
        "error": None,
    }


def build_review_prompt(
    build_plan: Optional[Dict[str, Any]],
    implementation_summary: str,
    files_changed: List[str],
    manual_criteria: Optional[List[str]] = None,
) -> str:
    """Build the review prompt based on available context."""

    if build_plan:
        # Review against build plan
        criteria = build_plan.get("success_criteria", [])
        risks = build_plan.get("risks", "Not specified")
        implementation_plan = build_plan.get("implementation_plan", [])
        topic = build_plan.get("topic", "Unknown")

        prompt = f"""REVIEW the following implementation against its build plan.

BUILD PLAN TOPIC:
{topic}

PLANNED IMPLEMENTATION:
{format_list(implementation_plan)}

SUCCESS CRITERIA TO VERIFY:
{format_list(criteria) if isinstance(criteria, list) else criteria}

IDENTIFIED RISKS (check if mitigated):
{risks}

ACTUAL IMPLEMENTATION:
{implementation_summary}

FILES CHANGED:
{format_list(files_changed) if files_changed else "Not specified"}

YOUR REVIEW MUST CHECK:
1. Did the implementation match the planned phases?
2. Are all success criteria met?
3. Were identified risks properly mitigated?
4. Is the system complete and functional?
5. Are there any security or compatibility issues (Windows/Linux/Mac)?
6. Is the code quality acceptable?

Be specific about what passes and what fails."""
    else:
        # Review against manual criteria
        criteria = manual_criteria or [
            "Implementation matches the stated requirements",
            "Code is readable and maintainable",
            "No obvious security vulnerabilities",
            "System compatibility (Windows/Linux/Mac) addressed",
            "Error handling is adequate",
        ]

        prompt = f"""REVIEW the following implementation using standard quality criteria.

REVIEW CRITERIA:
{format_list(criteria)}

ACTUAL IMPLEMENTATION:
{implementation_summary}

FILES CHANGED:
{format_list(files_changed) if files_changed else "Not specified"}

YOUR REVIEW MUST CHECK:
1. Does the implementation meet stated requirements?
2. Is code quality acceptable?
3. Are there security or compatibility issues?
4. Is error handling adequate?
5. What improvements are recommended?

Be specific about what passes and what fails."""

    return prompt


def parse_build_plan(plan_path: Path) -> Dict[str, Any]:
    """Parse a build plan markdown file into structured data."""

    content = plan_path.read_text(encoding="utf-8")

    plan = {
        "topic": extract_section_header(content, "Build Plan"),
        "status": extract_field(content, "Status"),
        "specification": {
            "architecture": extract_section(content, "Design Specification"),
            "components": extract_section(content, "Components"),
        },
        "council_decisions": {
            "architect": extract_section(content, "Architect"),
            "auditor_blockers": extract_section(content, "BLOCKER Issues"),
            "auditor_risks": extract_section(content, "Other Risks"),
            "contextualist": extract_section(content, "Integration Guidance"),
            "judge_decision": extract_section(content, "FINAL DECISION"),
        },
        "implementation_plan": extract_list_items(content, r"Implementation Plan"),
        "risks": extract_section(content, "Risks & Mitigations"),
        "success_criteria": extract_list_items(content, r"Success Criteria"),
    }

    return plan


def parse_review_output(review_text: str, build_plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse the review output into structured data."""

    # Extract verdict
    verdict_match = re.search(r"VERDICT:\s*(APPROVED|CONDITIONAL|REJECTED)", review_text, re.IGNORECASE)
    verdict = verdict_match.group(1).upper() if verdict_match else "UNKNOWN"

    # Parse criteria reviews
    passed_checks = []
    failed_checks = []
    warnings = []

    in_criteria_section = False
    for line in review_text.split("\n"):
        line = line.strip()

        if "CRITERIA REVIEW" in line or "REVIEW RESULTS" in line:
            in_criteria_section = True
            continue

        if in_criteria_section and (line.startswith("RECOMMENDATIONS") or line.startswith("##")):
            break

        # Match pattern: [Pass/Fail/Warning] - Criteria name
        match = re.match(r"\[(Pass|Fail|Warning)\]\s*-\s*(.+)", line, re.IGNORECASE)
        if match:
            status = match.group(1).upper()
            criteria = match.group(2)

            if status == "PASS":
                passed_checks.append(criteria)
            elif status == "FAIL":
                failed_checks.append(criteria)
            elif status == "WARNING":
                warnings.append(criteria)

    # If no structured criteria found, try to extract from verdict
    if not any([passed_checks, failed_checks, warnings]):
        if verdict == "APPROVED":
            passed_checks.append("Implementation meets requirements")
        elif verdict == "REJECTED":
            failed_checks.append("Implementation does not meet requirements")
        elif verdict == "CONDITIONAL":
            passed_checks.append("Implementation partially meets requirements")
            warnings.append("Conditions must be addressed before deployment")

    return {
        "recommendation": verdict,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "warnings": warnings,
        "build_plan_topic": build_plan.get("topic") if build_plan else "Manual Review",
    }


def extract_section_header(content: str, section_name: str) -> str:
    """Extract a section header from markdown."""
    pattern = rf"^#\+ {section_name}:?\s*(.+)$"
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_field(content: str, field_name: str) -> str:
    """Extract a field value from markdown."""
    pattern = rf"\*\*{field_name}:\*\*\s*(.+?)(?:\n|\*|$)"
    match = re.search(pattern, content, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_section(content: str, section_title: str) -> str:
    """Extract a section's content from markdown."""
    # Look for ## Section Title
    pattern = rf"^##\s+{re.escape(section_title)}.*?$\n(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()[:500]
    return ""


def extract_list_items(content: str, section_pattern: str) -> List[str]:
    """Extract list items from a section."""
    # Find the section
    section_pattern = rf"^##\s+.*?{section_pattern}.*?$"
    section_match = re.search(section_pattern, content, re.MULTILINE | re.IGNORECASE)

    if not section_match:
        return []

    # Extract content until next ## or end
    start_pos = section_match.end()
    next_section = re.search(r"\n^##", content[start_pos:], re.MULTILINE)
    end_pos = start_pos + next_section.start() if next_section else len(content)

    section_content = content[start_pos:end_pos]

    # Extract list items
    items = []
    for line in section_content.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
        elif re.match(r"^\d+\.\s+", line):
            items.append(re.sub(r"^\d+\.\s+", "", line))

    return items


def format_list(items: List[str]) -> str:
    """Format a list as markdown."""
    if not items:
        return "* (no items)"
    if isinstance(items, str):
        return items
    return "\n".join(f"- {item}" for item in items)


def quick_review(
    what_was_built: str,
    criteria: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Quick review without a full build plan.
    Useful for ad-hoc validation.

    Args:
        what_was_built: Summary of what was implemented
        criteria: Optional list of criteria to check

    Returns:
        Review results
    """
    return review_build(
        build_plan_path=None,
        implementation_summary=what_was_built,
        files_changed=None,
        manual_review_criteria=criteria,
    )


# For standalone testing
if __name__ == "__main__":
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # Example: Review with manual criteria
    result = quick_review(
        what_was_built="""Created a web scraper that:
- Fetches URLs using requests library
- Caches pages as markdown in .cache/ directory
- Handles UTF-8 encoding properly
- Works on Windows, Linux, and Mac

Files created:
- scraper.py (main scraper logic)
- cache.py (caching system)
- requirements.txt""",
        criteria=[
            "UTF-8 encoding properly handled",
            "Windows path compatibility",
            "Error handling for network failures",
            "Cache invalidation strategy",
        ]
    )

    if result["success"]:
        print("\n=== Review Results ===")
        print(f"Recommendation: {result['recommendation']}\n")
        print("Passed Checks:")
        for check in result["passed_checks"]:
            print(f"  ✓ {check}")
        print("\nFailed Checks:")
        for check in result["failed_checks"]:
            print(f"  ✗ {check}")
        print("\nWarnings:")
        for warning in result["warnings"]:
            print(f"  ⚠ {warning}")
    else:
        print(f"Error: {result['error']}")
