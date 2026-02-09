#!/usr/bin/env python3
"""
refine.py - Mode 2: Series refinement mode

Runs AI models in series with critical review at each step.
Haiku -> Sonnet -> Opus (Flash removed per Council feedback).

Includes Pass-Fail gates and rollback mechanism.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List

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
from models import REFINEMENT_MODELS
from schemas import QualityGate, RollbackStore, get_rollback_store

# Dashboard tracking (optional, gracefully degrades if not available)
try:
    dashboard_path = Path(__file__).parent.parent.parent.parent / "dashboard" / "backend"
    if str(dashboard_path) not in sys.path:
        sys.path.insert(0, str(dashboard_path))
    from council_tracker import track_call, get_session_id, TASK_REFINEMENT
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False


def refine(input_text: str, context: str = "") -> Dict[str, Any]:
    """
    Run refinement mode (series with critical review).

    Args:
        input_text: Text to refine (plan, design, etc.)
        context: Additional context

    Returns:
        Dictionary with:
            - success (bool)
            - refined_output (str): Final refined text
            - critiques (list): Critiques from each round
            - rollback_store (obj): For rolling back to previous state
            - error (str): Error if failed
    """
    gateway = get_gateway()
    rollback = get_rollback_store()

    print_safe(f"\n=== Council Refinement Mode ===")
    print_safe(f"Input: {input_text[:100]}...\n")

    rounds = REFINEMENT_MODELS["rounds"]
    current_state = {"original": input_text, "context": context}

    # Save original state for rollback
    rollback.save_state("refine_session", current_state)

    critiques = []
    refined_output = input_text

    for i, round_config in enumerate(rounds, 1):
        model = round_config["model"]
        role = round_config["role"]
        timeout = round_config.get("timeout", 90)

        print_safe(f"[Round {i}/{len(rounds)}] {model} - {role}...")

        # Build prompt for this round
        prompt = f"""You are a {role}. Your task is to review and refine the following text.

INPUT TO REFINE:
{refined_output}

{context}

Your CRITICAL REVIEW must:
1. Identify shortcomings and flaws
2. Check system compatibility (Windows/Linux/Mac)
3. Suggest specific improvements
4. Validate assumptions
5. If input is garbage, REJECT it and explain why

Your output should be the IMPROVED version. If the input is fundamentally flawed, explain why it cannot be refined.

Provide the refined text. Focus on progressive enhancement."""

        # Track start time for dashboard
        call_start = time.time()

        result = gateway.call_model(
            model=model,
            system_prompt=f"You are a {role}. Be thorough and specific.",
            user_prompt=prompt,
            timeout=timeout,
        )

        # Track to dashboard if available
        if TRACKING_AVAILABLE:
            duration = time.time() - call_start
            try:
                track_call(
                    model=model,
                    task_type=TASK_REFINEMENT,
                    response=result,
                    duration_seconds=duration,
                    session_id=get_session_id()
                )
            except Exception:
                pass  # Silently fail to not disrupt refinement

        if not result["success"]:
            # Try rollback
            original = rollback.get_original("refine_session")
            return {
                "success": False,
                "error": f"Round {i} failed: {result['error']}",
                "rollback_available": original is not None,
                "rollback_state": original,
            }

        round_output = result["content"]

        # Quality gate: Check if this round actually refined the input
        passes, reason = QualityGate.validate_refinement_output(round_output, i)
        if not passes:
            print_safe(f"\n⚠ Quality gate failed: {reason}")
            print_safe(f"   Rolling back to previous state...\n")

            # Rollback
            original = rollback.get_original("refine_session")
            if original:
                return {
                    "success": False,
                    "error": f"Quality gate failed at round {i}: {reason}",
                    "refined_output": original["original"],
                    "critiques": critiques,
                    "rollback_state": original,
                }

        # Save state for potential rollback
        rollback.save_state("refine_session", {
            "original": input_text,
            "context": context,
            "round": i,
            "output": round_output,
            "model": model,
        })

        critiques.append({
            "round": i,
            "model": model,
            "role": role,
            "critique": round_output[:500] if len(round_output) > 500 else round_output,
            "full_output": round_output,
        })

        refined_output = round_output
        print_safe(f"[OK] Round {i} completed ({result['tokens']} tokens)\n")

    print_safe("✓ Refinement complete\n")

    return {
        "success": True,
        "refined_output": refined_output,
        "critiques": critiques,
        "rollback_state": rollback.get_latest("refine_session"),
        "error": None,
    }


def rollback(session_id: str = "refine_session") -> Dict[str, Any]:
    """
    Rollback to a previous state.

    Args:
        session_id: Session identifier for rollback store

    Returns:
        Dictionary with rollback result
    """
    rollback = get_rollback_store()
    state = rollback.get_latest(session_id)

    if not state:
        return {
            "success": False,
            "error": "No previous state found to rollback to",
            "state": None,
        }

    return {
        "success": True,
        "state": state,
        "error": None,
    }


# For standalone testing
if __name__ == "__main__":
    import io

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    result = refine(
        "Create a web scraper that caches pages as markdown",
        context="Focus on Windows compatibility and encoding handling"
    )

    if result["success"]:
        print("\n=== Final Output ===")
        print(result["refined_output"][:500])
        print("\n=== Critiques ===")
        for c in result["critiques"]:
            print(f"\nRound {c['round']} ({c['model']}):")
            print(f"  {c['critique'][:200]}...")
    else:
        print(f"Error: {result['error']}")
