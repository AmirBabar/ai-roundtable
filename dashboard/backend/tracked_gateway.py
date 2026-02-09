#!/usr/bin/env python3
"""
tracked_gateway.py - Wrapper for CouncilGateway with automatic dashboard tracking

This module wraps the CouncilGateway class to automatically track all API calls
to the dashboard database with token usage, costs, and timing.

Usage:
    from tracked_gateway import get_tracked_gateway

    gateway = get_tracked_gateway()
    result = gateway.call_model(
        model="gemini-architect",
        system_prompt="You are an architect.",
        user_prompt="Design a system.",
        task_type="quick-verify",  # New parameter
        timeout=60
    )
    # Call is automatically tracked to dashboard
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add council scripts to path
COUNCIL_PATH = Path(__file__).parent.parent.parent / "skills" / "council" / "scripts"
sys.path.insert(0, str(COUNCIL_PATH))

from gateway import CouncilGateway, get_gateway
from tracker import track_gateway_response, track_api_call


class TrackedCouncilGateway:
    """
    Wrapper around CouncilGateway that automatically tracks API calls.

    Adds automatic dashboard tracking for all model calls with:
    - Token usage and cost calculation
    - Duration timing
    - Status and error tracking
    - Task type classification
    """

    def __init__(self, gateway: Optional[CouncilGateway] = None):
        """
        Initialize the tracked gateway.

        Args:
            gateway: Optional CouncilGateway instance (uses singleton if not provided)
        """
        self._gateway = gateway or get_gateway()
        self._default_task_type = "unknown"

    def call_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "unknown",
        timeout: Optional[int] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        session_id: Optional[str] = None,
        track: bool = True
    ) -> Dict[str, Any]:
        """
        Call a model via the gateway and track the call to dashboard.

        Args:
            model: Model identifier
            system_prompt: System message
            user_prompt: User message
            task_type: Type of task (quick-verify, security-audit, etc.)
            timeout: Request timeout in seconds
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            session_id: Optional session identifier
            track: Whether to track this call (default: True)

        Returns:
            Dictionary with:
                - success (bool)
                - content (str): Model response
                - model (str): Model that responded
                - tokens (int): Tokens used (if available)
                - error (str): Error message if failed
        """
        start_time = time.time()

        try:
            # Call the underlying gateway
            response = self._gateway.call_model(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
                temperature=temperature,
                max_tokens=max_tokens
            )

            duration = time.time() - start_time

            # Track to dashboard
            if track:
                track_gateway_response(
                    model=model,
                    task_type=task_type,
                    response=response,
                    duration_seconds=duration,
                    session_id=session_id
                )

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Track the error
            if track:
                track_api_call(
                    model=model,
                    task_type=task_type,
                    duration_seconds=duration,
                    status="error",
                    error_message=str(e)[:500],
                    session_id=session_id
                )

            # Re-raise the exception
            raise

    def set_default_task_type(self, task_type: str):
        """Set the default task type for calls."""
        self._default_task_type = task_type


# ============================================================================
# GLOBAL TRACKED GATEWAY INSTANCE
# ============================================================================
_tracked_gateway: Optional[TrackedCouncilGateway] = None


def get_tracked_gateway() -> TrackedCouncilGateway:
    """Get the global tracked gateway instance (singleton)."""
    global _tracked_gateway
    if _tracked_gateway is None:
        _tracked_gateway = TrackedCouncilGateway()
    return _tracked_gateway


# ============================================================================
# TASK TYPE CONSTANTS
# ============================================================================
# Standard task types for Council operations
TASK_TYPE_QUICK_VERIFY = "quick-verify"
TASK_TYPE_SECURITY_AUDIT = "security-audit"
TASK_TYPE_REPO_MAP = "repo-map"
TASK_TYPE_TEAM_DEBATE = "team-debate"
TASK_TYPE_BRAINSTORM = "brainstorm"
TASK_TYPE_REFINEMENT = "refinement"
TASK_TYPE_BUILD_PLANNING = "build-planning"
TASK_TYPE_DRIFT_CHECK = "drift-check"
TASK_TYPE_RESEARCH = "research"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
def quick_verify(
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 30,
    **kwargs
) -> Dict[str, Any]:
    """
    Quick verification call using fast model.

    Args:
        model: Model to use (default: gemini-flash if not specified)
        system_prompt: System message
        user_prompt: User message
        timeout: Timeout in seconds
        **kwargs: Additional arguments passed to call_model

    Returns:
        Response dictionary
    """
    gateway = get_tracked_gateway()
    return gateway.call_model(
        model=model or "gemini-flash",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task_type=TASK_TYPE_QUICK_VERIFY,
        timeout=timeout,
        **kwargs
    )


def security_audit(
    system_prompt: str,
    user_prompt: str,
    timeout: int = 180,
    model: str = "deepseek-security",
    **kwargs
) -> Dict[str, Any]:
    """
    Security audit call using DeepSeek R1.

    Args:
        system_prompt: System message
        user_prompt: User message
        timeout: Timeout in seconds
        model: Model to use
        **kwargs: Additional arguments passed to call_model

    Returns:
        Response dictionary
    """
    gateway = get_tracked_gateway()
    return gateway.call_model(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        task_type=TASK_TYPE_SECURITY_AUDIT,
        timeout=timeout,
        **kwargs
    )


def repo_map(
    codebase_path: str,
    query: str,
    timeout: int = 180,
    model: str = "kimi-researcher",
    **kwargs
) -> Dict[str, Any]:
    """
    Repository mapping call using Kimi's 256k context.

    Args:
        codebase_path: Path to codebase
        query: Query about codebase
        timeout: Timeout in seconds
        model: Model to use
        **kwargs: Additional arguments passed to call_model

    Returns:
        Response dictionary
    """
    gateway = get_tracked_gateway()

    system_prompt = f"""You are a codebase analyst with access to the repository at: {codebase_path}

Analyze the codebase structure and answer questions about:
- Architecture and patterns
- Dependencies and integration points
- File locations and purposes
- Historical decisions and rationale

Be specific and reference actual files when possible."""

    return gateway.call_model(
        model=model,
        system_prompt=system_prompt,
        user_prompt=query,
        task_type=TASK_TYPE_REPO_MAP,
        timeout=timeout,
        **kwargs
    )


# ============================================================================
# CLI FOR TESTING
# ============================================================================
if __name__ == "__main__":
    import sys

    # Fix stdout encoding for Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=== Tracked Gateway Test ===\n")

    # Test basic call
    print("Testing quick_verify...")
    result = quick_verify(
        model="gemini-flash",
        system_prompt="You are a helpful assistant.",
        user_prompt="Say 'Test successful' in one sentence.",
        timeout=30
    )

    if result["success"]:
        print(f"✓ Call tracked successfully")
        print(f"  Model: {result['model']}")
        print(f"  Tokens: {result.get('tokens', 'N/A')}")
        print(f"  Response: {result['content'][:100]}...")
    else:
        print(f"✗ Call failed: {result.get('error')}")

    print("\nTest complete. Check dashboard for tracked calls.")
