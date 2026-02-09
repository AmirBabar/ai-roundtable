#!/usr/bin/env python3
"""
Example: Integrating dashboard tracking with Council skills

This file demonstrates how to add automatic dashboard tracking to any Council skill.
"""

# ============================================================================
# METHOD 1: Simple import and call (recommended for most cases)
# ============================================================================
from council_tracker import track_call, get_session_id

def my_skill_function():
    """Example skill function with tracking."""
    import sys
    from pathlib import Path

    # Add council scripts to path
    council_path = Path(__file__).parent.parent.parent / "skills" / "council" / "scripts"
    sys.path.insert(0, str(council_path))

    from gateway import get_gateway

    gateway = get_gateway()
    model = "gemini-flash"

    start_time = time.time()
    response = gateway.call_model(
        model=model,
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello"
    )
    duration = time.time() - start_time

    # Track the call
    track_call(
        model=model,
        task_type="my-custom-task",
        response=response,
        duration_seconds=duration,
        session_id=get_session_id()
    )

    return response


# ============================================================================
# METHOD 2: Using the context manager (cleaner for complex functions)
# ============================================================================
import time
from council_tracker import track_time

def my_skill_function_v2():
    """Example using context manager."""
    from gateway import get_gateway

    gateway = get_gateway()
    model = "gemini-architect"

    with track_time(model, "quick-verify") as t:
        response = gateway.call_model(
            model=model,
            system_prompt="You are an architect.",
            user_prompt="Design a system"
        )
        # Set the result for tracking
        t.set_result(response)

    return response


# ============================================================================
# METHOD 3: Using the decorator (best for reusable functions)
# ============================================================================
from council_tracker import tracked_call, TASK_QUICK_VERIFY

@tracked_call(TASK_QUICK_VERIFY, model_arg="model")
def verify_with_gateway(prompt: str, model: str = "gemini-flash"):
    """Auto-tracked verification function."""
    from gateway import get_gateway
    gateway = get_gateway()
    return gateway.call_model(
        model=model,
        system_prompt="You are a verifier.",
        user_prompt=prompt
    )


# ============================================================================
# METHOD 4: Manual tracking (when you have token counts from elsewhere)
# ============================================================================
from council_tracker import track_manual

def track_external_api_call(model: str, tokens: int, cost: float, duration: float):
    """Track an API call made outside the gateway."""
    track_manual(
        model=model,
        task_type="external-api",
        total_tokens=tokens,
        duration_seconds=duration,
        status="success"
    )


# ============================================================================
# COMPLETE EXAMPLE: Updated Council Skill with Tracking
# ============================================================================
"""
To add tracking to an existing Council skill:

1. Add these imports at the top:
   from council_tracker import track_call, get_session_id, TASK_QUICK_VERIFY
   import time

2. Wrap your gateway.call_model() calls:

   # Before:
   result = gateway.call_model(model, system_prompt, user_prompt)

   # After:
   start = time.time()
   result = gateway.call_model(model, system_prompt, user_prompt)
   duration = time.time() - start
   track_call(model, TASK_QUICK_VERIFY, result, duration, get_session_id())

3. That's it! Your skill is now tracking to the dashboard.

Full example:
"""
import sys
import time
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "council" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard" / "backend"))

from gateway import get_gateway
from council_tracker import track_call, get_session_id, TASK_QUICK_VERIFY

def quick_verify_with_tracking(prompt: str, model: str = "gemini-flash"):
    """
    Quick verification with automatic dashboard tracking.

    This function demonstrates the minimal changes needed to add tracking:
    1. Track start time
    2. Call gateway as usual
    3. Track duration and log to dashboard
    """
    gateway = get_gateway()

    # Track start time
    start_time = time.time()

    # Call gateway (existing code - no changes needed)
    response = gateway.call_model(
        model=model,
        system_prompt="You are a logic validator. Check for flaws.",
        user_prompt=prompt
    )

    # Calculate duration
    duration = time.time() - start_time

    # Track to dashboard (single line addition)
    track_call(
        model=model,
        task_type=TASK_QUICK_VERIFY,
        response=response,
        duration_seconds=duration,
        session_id=get_session_id()
    )

    return response


# ============================================================================
# TESTING
# ============================================================================
if __name__ == "__main__":
    print("=== Testing Dashboard Integration ===\n")

    # Test method 1
    print("Method 1: Direct tracking")
    result = my_skill_function()
    print(f"  Success: {result.get('success')}")
    print(f"  Tokens: {result.get('tokens', 'N/A')}")

    time.sleep(1)

    # Test method 2
    print("\nMethod 2: Context manager")
    result = my_skill_function_v2()
    print(f"  Success: {result.get('success')}")
    print(f"  Tokens: {result.get('tokens', 'N/A')}")

    time.sleep(1)

    # Test method 3
    print("\nMethod 3: Decorator")
    result = verify_with_gateway("Check this logic")
    print(f"  Success: {result.get('success')}")
    print(f"  Tokens: {result.get('tokens', 'N/A')}")

    print("\nAll methods tracked to dashboard!")
    print(f"View at: http://127.0.0.1:8080")
