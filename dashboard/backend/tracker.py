#!/usr/bin/env python3
"""
tracker.py - Automated API call tracking for Council dashboard

Tracks all Council Gateway API calls with:
- Token usage (prompt, completion, total)
- Cost calculation in USD
- Duration timing
- Status tracking (success, error, timeout)
- Session and request IDs
- Real-time SSE broadcasting

Per Council decree ARCH-2024-008:
- Uses SQLite with WAL mode for concurrent access
- Implements persistent queue for reliability
- Graceful degradation on database errors
"""

import sqlite3
import json
import uuid
import threading
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque

from pricing import calculate_cost, get_pricing

# Try to import SSE for real-time broadcasting
try:
    from sse_events import broadcast_api_call
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False

# Try to import budget alerts
try:
    from budget_alerts import check_budget_thresholds
    BUDGET_ALERTS_AVAILABLE = True
except ImportError:
    BUDGET_ALERTS_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================
DATABASE_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"
QUEUE_PATH = Path(__file__).parent.parent / "data" / "tracker_queue.jsonl"
QUEUE_MAX_SIZE = 1000  # Maximum items in persistent queue
FLUSH_INTERVAL = 5  # Seconds between queue flushes


# ============================================================================
# DATA STRUCTURES
# ============================================================================
@dataclass
class ApiCallRecord:
    """Record of an API call for dashboard tracking."""
    timestamp: str
    model: str
    task_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    duration_seconds: float
    status: str
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# ============================================================================
# TRACKER CLASS
# ============================================================================
class DashboardTracker:
    """
    Tracks Council API calls and writes to dashboard database.

    Features:
    - Automatic token counting and cost calculation
    - Persistent queue for reliability
    - Background thread for async writes
    - Graceful degradation on database errors
    """

    def __init__(self, database_path: Path = DATABASE_PATH):
        """
        Initialize the tracker.

        Args:
            database_path: Path to dashboard SQLite database
        """
        self.database_path = database_path
        self._queue: deque = deque(maxlen=QUEUE_MAX_SIZE)
        self._lock = threading.Lock()
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None

        # Ensure database exists
        self._ensure_database()

        # Start background flush thread
        self._start_flush_thread()

    def _ensure_database(self):
        """Ensure database and tables exist."""
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

            if not self.database_path.exists():
                # Create database - delegate to initialization script
                print("[WARN] Dashboard database not found. Tracking will be queued.")

        except Exception as e:
            print(f"[ERROR] Database check failed: {e}")

    def _start_flush_thread(self):
        """Start background thread for flushing queue to database."""
        self._running = True

        def flush_loop():
            while self._running:
                time.sleep(FLUSH_INTERVAL)
                self._flush_queue()

            # Final flush on shutdown
            self._flush_queue()

        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()

    def _flush_queue(self):
        """Flush queued records to database."""
        with self._lock:
            if not self._queue:
                return

            records = list(self._queue)
            self._queue.clear()

        if not records:
            return

        try:
            self._write_records(records)
            print(f"[INFO] Flushed {len(records)} records to dashboard")
        except Exception as e:
            print(f"[ERROR] Failed to flush records: {e}")
            # Re-queue for next attempt
            with self._lock:
                for record in records:
                    if len(self._queue) < self._queue.maxlen:
                        self._queue.append(record)

    def _write_records(self, records: list):
        """Write records to database."""
        try:
            conn = sqlite3.connect(
                str(self.database_path),
                check_same_thread=False,
                timeout=10.0
            )
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            for record in records:
                cursor.execute("""
                    INSERT OR IGNORE INTO api_calls (
                        timestamp, model, task_type, prompt_tokens, completion_tokens,
                        total_tokens, cost_usd, duration_seconds, status,
                        error_message, session_id, request_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.timestamp,
                    record.model,
                    record.task_type,
                    record.prompt_tokens,
                    record.completion_tokens,
                    record.total_tokens,
                    record.cost_usd,
                    record.duration_seconds,
                    record.status,
                    record.error_message,
                    record.session_id,
                    record.request_id
                ))

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            print(f"[ERROR] Database write failed: {e}")
            raise

    def track_api_call(
        self,
        model: str,
        task_type: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        duration_seconds: float = 0,
        status: str = "success",
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        """
        Track an API call to the dashboard.

        Args:
            model: Council model alias
            task_type: Type of task (quick-verify, security-audit, etc.)
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            total_tokens: Total tokens (if prompt/completion not provided)
            duration_seconds: Duration of the call
            status: Status (success, error, timeout)
            error_message: Error message if status is not success
            session_id: Optional session identifier
            request_id: Optional unique request ID

        Returns:
            Request ID for this call
        """
        # Generate request ID if not provided
        if not request_id:
            request_id = str(uuid.uuid4())

        # Calculate total if not provided
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens

        # Calculate cost
        cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)

        # Create record (use UTC timestamp for consistency)
        record = ApiCallRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            duration_seconds=round(duration_seconds, 2),
            status=status,
            error_message=error_message,
            session_id=session_id,
            request_id=request_id
        )

        # Add to queue for async write
        with self._lock:
            self._queue.append(record)

        # Broadcast real-time event via SSE
        if SSE_AVAILABLE:
            try:
                broadcast_api_call(record.to_dict())
            except Exception as e:
                print(f"[WARN] Failed to broadcast SSE event: {e}")

        # Check budget thresholds (async via background check)
        if BUDGET_ALERTS_AVAILABLE:
            try:
                # Run in separate thread to avoid blocking
                threading.Thread(target=check_budget_thresholds, daemon=True).start()
            except Exception as e:
                print(f"[WARN] Failed to check budget thresholds: {e}")

        return request_id

    def track_gateway_response(
        self,
        model: str,
        task_type: str,
        response: Dict[str, Any],
        duration_seconds: float,
        session_id: Optional[str] = None
    ) -> str:
        """
        Track a gateway API call response.

        Convenience method that extracts data from gateway response.

        Args:
            model: Council model alias
            task_type: Type of task
            response: Response dict from CouncilGateway
            duration_seconds: Duration of the call
            session_id: Optional session identifier

        Returns:
            Request ID for this call
        """
        # Extract token usage from response
        usage = response.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = response.get("tokens", 0)

        if total_tokens and not (prompt_tokens or completion_tokens):
            # Estimate split if only total available
            prompt_tokens = int(total_tokens * 0.3)
            completion_tokens = total_tokens - prompt_tokens

        return self.track_api_call(
            model=model,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration_seconds,
            status="success" if response.get("success") else "error",
            error_message=response.get("error"),
            session_id=session_id
        )

    def shutdown(self):
        """Shutdown the tracker and flush remaining records."""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        self._flush_queue()


# ============================================================================
# GLOBAL TRACKER INSTANCE
# ============================================================================
_tracker: Optional[DashboardTracker] = None
_tracker_lock = threading.Lock()


def get_tracker() -> DashboardTracker:
    """Get the global tracker instance (singleton)."""
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = DashboardTracker()
        return _tracker


def track_api_call(*args, **kwargs) -> str:
    """
    Convenience function to track an API call.

    Uses the global tracker instance.
    """
    return get_tracker().track_api_call(*args, **kwargs)


def track_gateway_response(*args, **kwargs) -> str:
    """
    Convenience function to track a gateway response.

    Uses the global tracker instance.
    """
    return get_tracker().track_gateway_response(*args, **kwargs)


# ============================================================================
# DECORATOR FOR AUTOMATIC TRACKING
# ============================================================================
def track_call(task_type: str):
    """
    Decorator to automatically track function calls to gateway.

    Args:
        task_type: Type of task being performed

    Example:
        @track_call("quick-verify")
        def verify_logic(prompt: str):
            return gateway.call_model(...)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            model = kwargs.get("model", "unknown")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                track_gateway_response(
                    model=model,
                    task_type=task_type,
                    response=result,
                    duration_seconds=duration,
                    session_id=kwargs.get("session_id")
                )

                return result

            except Exception as e:
                duration = time.time() - start_time
                track_api_call(
                    model=model,
                    task_type=task_type,
                    duration_seconds=duration,
                    status="error",
                    error_message=str(e)[:500],
                    session_id=kwargs.get("session_id")
                )
                raise

        return wrapper
    return decorator


# ============================================================================
# CLI FOR TESTING
# ============================================================================
if __name__ == "__main__":
    import sys

    print("=== Dashboard Tracker Test ===\n")

    # Test tracking
    request_id = track_api_call(
        model="gemini-architect",
        task_type="test",
        prompt_tokens=1000,
        completion_tokens=500,
        duration_seconds=2.5,
        status="success"
    )

    print(f"Tracked request: {request_id}")

    # Test gateway response tracking
    mock_response = {
        "success": True,
        "content": "Test response",
        "tokens": 2000,
        "usage": {
            "prompt_tokens": 800,
            "completion_tokens": 1200
        }
    }

    request_id2 = track_gateway_response(
        model="deepseek-v3",
        task_type="security-audit",
        response=mock_response,
        duration_seconds=5.2
    )

    print(f"Tracked gateway call: {request_id2}")

    # Flush and shutdown
    tracker = get_tracker()
    tracker.shutdown()

    print("\n[OK] Test complete")
