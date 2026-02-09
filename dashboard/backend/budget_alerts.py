#!/usr/bin/env python3
"""
Budget Alert System for Council Dashboard

Monitors API spending and generates alerts when thresholds are exceeded.
Supports daily, weekly, and monthly budget tracking.

Usage:
    from budget_alerts import check_budget_thresholds, set_budget_threshold

    # Set a daily budget of $5.00
    set_budget_threshold("daily", 5.00)

    # Check if current spending exceeds thresholds
    alerts = check_budget_thresholds()
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

# Database path
DATABASE_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"

# Default budget thresholds (USD)
DEFAULT_THRESHOLDS = {
    "daily": 10.0,
    "weekly": 50.0,
    "monthly": 200.0
}


# ============================================================================
# SETTINGS MANAGEMENT
# ============================================================================
def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value from the database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            value = row[0]
            # Try to convert to float for numeric values
            try:
                return float(value)
            except ValueError:
                return value
        return default
    except Exception as e:
        print(f"[ERROR] Failed to get setting {key}: {e}")
        return default


def set_setting(key: str, value: Any) -> bool:
    """Set a setting value in the database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (key, str(value)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to set setting {key}: {e}")
        return False


def set_budget_threshold(period: str, amount_usd: float) -> bool:
    """
    Set a budget threshold for a time period

    Args:
        period: 'daily', 'weekly', or 'monthly'
        amount_usd: Budget amount in USD

    Returns:
        True if successful, False otherwise
    """
    if period not in ["daily", "weekly", "monthly"]:
        print(f"[ERROR] Invalid period: {period}")
        return False

    return set_setting(f"budget_threshold_{period}", amount_usd)


def get_budget_threshold(period: str) -> float:
    """
    Get the budget threshold for a time period

    Args:
        period: 'daily', 'weekly', or 'monthly'

    Returns:
        Budget threshold in USD (returns default if not set)
    """
    return get_setting(f"budget_threshold_{period}", DEFAULT_THRESHOLDS.get(period, 0))


# ============================================================================
# SPENDING CALCULATION
# ============================================================================
def get_spending(period: str) -> float:
    """
    Calculate total spending for a time period

    Args:
        period: 'daily', 'weekly', or 'monthly'

    Returns:
        Total spending in USD
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Calculate time range
        now = datetime.now()
        if period == "daily":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            # Start of week (Monday)
            start_time = now - timedelta(days=now.weekday())
            start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "monthly":
            # Start of month
            start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return 0.0

        # Query total spending (use localtime to match tracker timestamps)
        cursor.execute("""
            SELECT COALESCE(SUM(cost_usd), 0) as total
            FROM api_calls
            WHERE status = 'success'
              AND datetime(timestamp) >= datetime(?)
        """, (start_time.isoformat(),))

        result = cursor.fetchone()
        conn.close()

        return float(result[0]) if result else 0.0
    except Exception as e:
        print(f"[ERROR] Failed to calculate spending: {e}")
        return 0.0


def get_spending_breakdown() -> Dict[str, Dict[str, Any]]:
    """
    Get detailed spending breakdown by period

    Returns:
        Dictionary with spending info for daily, weekly, monthly
    """
    breakdown = {}
    for period in ["daily", "weekly", "monthly"]:
        threshold = get_budget_threshold(period)
        spent = get_spending(period)
        percentage = (spent / threshold * 100) if threshold > 0 else 0

        breakdown[period] = {
            "spent_usd": round(spent, 4),
            "threshold_usd": round(threshold, 2),
            "remaining_usd": round(max(0, threshold - spent), 4),
            "percentage": min(100, round(percentage, 1)),
            "over_budget": spent > threshold
        }

    return breakdown


# ============================================================================
# ALERT GENERATION
# ============================================================================
def create_alert(alert_type: str, threshold_usd: float, actual_usd: float) -> int:
    """
    Create a budget alert in the database

    Args:
        alert_type: 'daily', 'weekly', or 'monthly'
        threshold_usd: Budget threshold that was exceeded
        actual_usd: Actual spending amount

    Returns:
        Alert ID if created, None otherwise
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO budget_alerts (alert_type, threshold_usd, actual_usd)
            VALUES (?, ?, ?)
        """, (alert_type, threshold_usd, actual_usd))
        conn.commit()
        alert_id = cursor.lastrowid
        conn.close()

        print(f"[ALERT] Budget alert created: {alert_type} - ${actual_usd:.4f} / ${threshold_usd:.2f}")
        return alert_id
    except Exception as e:
        print(f"[ERROR] Failed to create alert: {e}")
        return None


def check_budget_thresholds() -> List[Dict[str, Any]]:
    """
    Check all budget thresholds and generate alerts if exceeded

    Returns:
        List of new alerts (dictionaries)
    """
    new_alerts = []
    now = datetime.now().isoformat()

    for period in ["daily", "weekly", "monthly"]:
        threshold = get_budget_threshold(period)
        spent = get_spending(period)

        # Check if over budget
        if spent > threshold:
            # Check if we already have an unacknowledged alert for this period today
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()

                # Check for recent unacknowledged alert (within last hour for same period)
                cursor.execute("""
                    SELECT id FROM budget_alerts
                    WHERE alert_type = ?
                      AND acknowledged = 0
                      AND datetime(timestamp) > datetime('now', '-1 hour')
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (period,))

                existing = cursor.fetchone()
                conn.close()

                # Only create new alert if no recent unacknowledged alert
                if not existing:
                    alert_id = create_alert(period, threshold, spent)
                    if alert_id:
                        # Broadcast alert via SSE
                        try:
                            from sse_events import broadcast_alert
                            broadcast_alert({
                                "id": alert_id,
                                "type": period,
                                "threshold_usd": threshold,
                                "actual_usd": spent,
                                "overage": spent - threshold,
                                "timestamp": now
                            })
                        except ImportError:
                            pass  # SSE not available

                        new_alerts.append({
                            "id": alert_id,
                            "type": period,
                            "threshold_usd": threshold,
                            "actual_usd": spent,
                            "overage": spent - threshold,
                            "timestamp": now
                        })
            except Exception as e:
                print(f"[ERROR] Failed to check existing alerts: {e}")

    return new_alerts


def acknowledge_alert(alert_id: int) -> bool:
    """
    Mark an alert as acknowledged

    Args:
        alert_id: Alert ID to acknowledge

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE budget_alerts
            SET acknowledged = 1
            WHERE id = ?
        """, (alert_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to acknowledge alert: {e}")
        return False


# ============================================================================
# ALERT RETRIEVAL
# ============================================================================
def get_recent_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent budget alerts

    Args:
        limit: Maximum number of alerts to return

    Returns:
        List of alert dictionaries
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, alert_type, threshold_usd, actual_usd,
                   (actual_usd - threshold_usd) as overage,
                   acknowledged, timestamp
            FROM budget_alerts
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return alerts
    except Exception as e:
        print(f"[ERROR] Failed to get alerts: {e}")
        return []


def get_unacknowledged_alerts() -> List[Dict[str, Any]]:
    """
    Get all unacknowledged alerts

    Returns:
        List of unacknowledged alert dictionaries
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, alert_type, threshold_usd, actual_usd,
                   (actual_usd - threshold_usd) as overage,
                   timestamp
            FROM budget_alerts
            WHERE acknowledged = 0
            ORDER BY timestamp DESC
        """)

        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return alerts
    except Exception as e:
        print(f"[ERROR] Failed to get unacknowledged alerts: {e}")
        return []


# ============================================================================
# BUDGET STATUS SUMMARY
# ============================================================================
def get_budget_status() -> Dict[str, Any]:
    """
    Get complete budget status summary

    Returns:
        Dictionary with spending breakdown, alerts, and status
    """
    spending = get_spending_breakdown()
    unacknowledged = get_unacknowledged_alerts()

    # Determine overall status
    has_over_budget = any(p["over_budget"] for p in spending.values())
    has_unacknowledged = len(unacknowledged) > 0

    status = "ok"
    if has_over_budget:
        status = "critical"
    elif has_unacknowledged:
        status = "warning"

    return {
        "spending": spending,
        "unacknowledged_alerts": unacknowledged,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
