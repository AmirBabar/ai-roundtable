#!/usr/bin/env python3
"""
council_tracker.py - Dashboard tracking integration for Council skills

Easy-to-use tracking functions for Council skills.
Import this module to automatically track all Council API calls to the dashboard.

Usage:
    from council_tracker import track_call, get_session_id

    # Track a model call
    result = gateway.call_model(...)
    track_call(
        model="gemini-architect",
        task_type="quick-verify",
        response=result,
        duration_seconds=2.5,
        session_id=get_session_id()
    )

Or use the decorator:
    from council_tracker import tracked_call

    @tracked_call("quick-verify")
    def verify_logic(prompt):
        return gateway.call_model(...)
"""

import os
import uuid
import time
from typing import Dict, Any, Optional
from pathlib import Path

# Add dashboard backend to path
DASHBOARD_PATH = Path(__file__).parent.parent.parent / "dashboard" / "backend"
import sys
if str(DASHBOARD_PATH) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_PATH))

# Import tracker
try:
    from tracker import track_api_call, track_gateway_response
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False
    print("[WARN] Dashboard tracking not available. Install tracker.py to enable.")


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================
_session_id: Optional[str] = None


def get_session_id() -> str:
    """
    Get or create a session ID for tracking.

    Session ID persists for the duration of the Python process.
    All calls in the same session share this ID.

    Returns:
        Session ID string
    """
    global _session_id
    if _session_id is None:
        _session_id = os.environ.get("COUNCIL_SESSION_ID", str(uuid.uuid4()))
    return _session_id


def set_session_id(session_id: str):
    """Set a custom session ID."""
    global _session_id
    _session_id = session_id


# ============================================================================
# TRACKING FUNCTIONS
# ============================================================================
def track_call(
    model: str,
    task_type: str,
    response: Dict[str, Any],
    duration_seconds: float,
    session_id: Optional[str] = None
) -> Optional[str]:
    """
    Track a Council API call to the dashboard.

    Args:
        model: Council model alias (e.g., "gemini-architect")
        task_type: Task type (quick-verify, security-audit, etc.)
        response: Response dictionary from gateway
        duration_seconds: Duration of the call
        session_id: Optional session ID (uses default if not provided)

    Returns:
        Request ID if tracking succeeded, None otherwise
    """
    if not TRACKING_AVAILABLE:
        return None

    try:
        return track_gateway_response(
            model=model,
            task_type=task_type,
            response=response,
            duration_seconds=duration_seconds,
            session_id=session_id or get_session_id()
        )
    except Exception as e:
        # Silently fail to avoid disrupting Council operations
        print(f"[DEBUG] Tracking failed: {e}")
        return None


def track_manual(
    model: str,
    task_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    duration_seconds: float = 0,
    status: str = "success",
    error_message: Optional[str] = None,
    session_id: Optional[str] = None
) -> Optional[str]:
    """
    Manually track a call (when you don't have a gateway response).

    Args:
        model: Council model alias
        task_type: Task type
        prompt_tokens: Input tokens
        completion_tokens: Output tokens
        total_tokens: Total tokens
        duration_seconds: Duration
        status: Status (success, error, timeout)
        error_message: Error message if not success
        session_id: Optional session ID

    Returns:
        Request ID if tracking succeeded, None otherwise
    """
    if not TRACKING_AVAILABLE:
        return None

    try:
        return track_api_call(
            model=model,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration_seconds,
            status=status,
            error_message=error_message,
            session_id=session_id or get_session_id()
        )
    except Exception as e:
        print(f"[DEBUG] Tracking failed: {e}")
        return None


# ============================================================================
# DECORATORS
# ============================================================================
def tracked_call(task_type: str, model_arg: str = "model"):
    """
    Decorator to automatically track function calls to gateway.

    Args:
        task_type: Type of task being performed
        model_arg: Name of argument containing model name (default: "model")

    Example:
        @tracked_call("quick-verify")
        def verify_logic(prompt: str, model: str = "gemini-flash"):
            return gateway.call_model(model=model, ...)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            model = kwargs.get(model_arg, "unknown")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                track_call(
                    model=model,
                    task_type=task_type,
                    response=result,
                    duration_seconds=duration
                )

                return result

            except Exception as e:
                duration = time.time() - start_time
                track_manual(
                    model=model,
                    task_type=task_type,
                    duration_seconds=duration,
                    status="error",
                    error_message=str(e)[:500]
                )
                raise

        return wrapper
    return decorator


# ============================================================================
# TASK TYPE CONSTANTS
# ============================================================================
TASK_QUICK_VERIFY = "quick-verify"
TASK_SECURITY_AUDIT = "security-audit"
TASK_REPO_MAP = "repo-map"
TASK_TEAM_DEBATE = "team-debate"
TASK_BRAINSTORM = "brainstorm"
TASK_REFINEMENT = "refinement"
TASK_BUILD_PLANNING = "build-planning"
TASK_DRIFT_CHECK = "drift-check"
TASK_RESEARCH = "research"


# ============================================================================
# CONTEXT MANAGER FOR TIMING
# ============================================================================
class track_time:
    """
    Context manager for tracking timed operations.

    Example:
        with track_time("gemini-architect", "quick-verify") as t:
            result = gateway.call_model(...)
            t.set_result(result)
    """

    def __init__(self, model: str, task_type: str, session_id: Optional[str] = None):
        self.model = model
        self.task_type = task_type
        self.session_id = session_id or get_session_id()
        self.start_time = None
        self.response = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is None and self.response:
            # Success with response
            track_call(
                model=self.model,
                task_type=self.task_type,
                response=self.response,
                duration_seconds=duration,
                session_id=self.session_id
            )
        else:
            # Error or no response
            track_manual(
                model=self.model,
                task_type=self.task_type,
                duration_seconds=duration,
                status="error" if exc_type else "success",
                error_message=str(exc_val)[:500] if exc_val else None
            )
        return False  # Don't suppress exceptions

    def set_result(self, response: Dict[str, Any]):
        """Set the gateway response for tracking."""
        self.response = response


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
def is_available() -> bool:
    """Check if dashboard tracking is available."""
    return TRACKING_AVAILABLE


def get_dashboard_url() -> str:
    """Get the dashboard URL."""
    return "http://127.0.0.1:8080"


if __name__ == "__main__":
    # Test the module
    print("=== Council Tracker Test ===\n")
    print(f"Tracking available: {is_available()}")
    print(f"Session ID: {get_session_id()}")
    print(f"Dashboard URL: {get_dashboard_url()}")

    # Test manual tracking
    if is_available():
        request_id = track_manual(
            model="gemini-flash",
            task_type="test",
            total_tokens=1000,
            duration_seconds=1.5
        )
        print(f"\nTracked test call: {request_id}")
