#!/usr/bin/env python3
"""
Council Memory API Integration for Dashboard

Exposes data from council_memory.db for dashboard visualization:
- Insights: Learned patterns and observations
- Sessions: Session tracking with metadata
- Events: System events and activity log
- Decisions: System decisions (tier 2)
- Constraints: Core constraints (tier 1)

Author: Council Dashboard Team
Version: 1.0.0
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Council Memory database path (using the data folder as canonical location)
COUNCIL_MEMORY_DB = Path(__file__).parent.parent.parent / "memory" / "data" / "council_memory.db"


def get_memory_stats() -> Dict[str, Any]:
    """
    Get Council Memory statistics.

    Returns counts for all major tables and recent activity metrics.
    """
    if not COUNCIL_MEMORY_DB.exists():
        return {
            "error": "Council Memory database not found",
            "path": str(COUNCIL_MEMORY_DB)
        }

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        cursor = conn.cursor()

        stats = {}

        # Get table counts
        tables_to_check = [
            'events', 'atomic_facts', 'category_summaries',
            'raw_insights_log', 'decisions', 'constraints',
            'preferences', 'error_patterns', 'validation_issues',
            'session_continuity', 'circuit_breaker_state'
        ]

        # Map actual table names to expected output names
        table_name_map = {
            'raw_insights_log': 'insights'  # For backwards compatibility with frontend
        }

        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                # Use mapped name for output key if mapping exists
                output_name = table_name_map.get(table, table)
                stats[f"{output_name}_count"] = count
            except sqlite3.OperationalError:
                # Table doesn't exist
                output_name = table_name_map.get(table, table)
                stats[f"{output_name}_count"] = 0

        # Recent activity (24h)
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM events
                WHERE timestamp >= datetime('now', '-24 hours')
            """)
            stats['events_last_24h'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['events_last_24h'] = 0

        # Recent activity (7d)
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM events
                WHERE timestamp >= datetime('now', '-7 days')
            """)
            stats['events_last_7d'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['events_last_7d'] = 0

        # Sessions count (distinct session_ids from events)
        try:
            cursor.execute("""
                SELECT COUNT(DISTINCT session_id)
                FROM events
                WHERE session_id IS NOT NULL AND session_id != ''
            """)
            stats['sessions_count'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['sessions_count'] = 0

        # Database size
        stats['db_size_bytes'] = COUNCIL_MEMORY_DB.stat().st_size
        stats['db_size_mb'] = round(stats['db_size_bytes'] / (1024 * 1024), 2)

        conn.close()
        return stats

    except Exception as e:
        return {"error": str(e), "path": str(COUNCIL_MEMORY_DB)}


def get_recent_insights(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent insights from Council Memory.

    Args:
        limit: Maximum number of insights to return

    Returns:
        List of insight dictionaries with content, category, confidence, etc.
    """
    if not COUNCIL_MEMORY_DB.exists():
        return []

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if raw_insights_log table exists (this is where insights are stored)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='raw_insights_log'
        """)
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("""
            SELECT
                id,
                captured_at,
                source_type,
                content,
                session_id,
                metadata,
                is_promoted,
                created_at
            FROM raw_insights_log
            ORDER BY captured_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        # Transform to expected format
        results = []
        for row in rows:
            # Parse source_type as category
            source_type = row['source_type'] or 'general'
            results.append({
                'id': row['id'],
                'content': row['content'],
                'category': source_type,
                'confidence': None,  # raw_insights_log doesn't have confidence
                'created_at': row['captured_at'],
                'session_id': row['session_id'],
                'metadata': row['metadata']
            })

        return results

    except Exception as e:
        print(f"[ERROR] get_recent_insights failed: {e}")
        return []


def get_recent_atomic_facts(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent atomic facts from Council Memory.

    Args:
        limit: Maximum number of facts to return

    Returns:
        List of fact dictionaries with content, category, confidence, etc.
    """
    if not COUNCIL_MEMORY_DB.exists():
        return []

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if atomic_facts table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='atomic_facts'
        """)
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("""
            SELECT
                fact_id,
                content,
                category,
                confidence,
                observation_count,
                first_observed,
                last_confirmed,
                created_at,
                is_active
            FROM atomic_facts
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    except Exception as e:
        print(f"[ERROR] get_recent_atomic_facts failed: {e}")
        return []


def get_recent_sessions(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent sessions from Council Memory.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session dictionaries with metadata
    """
    if not COUNCIL_MEMORY_DB.exists():
        return []

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Sessions aren't stored in a sessions table - extract from events
        # Group events by session_id to get session info
        cursor.execute("""
            SELECT
                session_id,
                MIN(timestamp) as start_time,
                MAX(timestamp) as last_activity,
                COUNT(*) as event_count,
                SUM(CASE WHEN event_type = 'user_input' THEN 1 ELSE 0 END) as user_inputs,
                SUM(CASE WHEN event_type = 'agent_response' THEN 1 ELSE 0 END) as agent_responses,
                SUM(CASE WHEN event_type = 'tool_failure' OR event_type = 'error' THEN 1 ELSE 0 END) as errors
            FROM events
            WHERE session_id IS NOT NULL AND session_id != ''
            GROUP BY session_id
            ORDER BY last_activity DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        # Transform to expected format
        results = []
        for row in rows:
            # Calculate duration
            start_time = row['start_time']
            last_activity = row['last_activity']
            try:
                from datetime import datetime
                if start_time and last_activity:
                    start = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                    last = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                    duration_seconds = int((last - start).total_seconds())
                else:
                    duration_seconds = None
            except:
                duration_seconds = None

            results.append({
                'session_id': row['session_id'],
                'start_time': row['start_time'],
                'last_activity': row['last_activity'],
                'duration_seconds': duration_seconds,
                'message_count': row['user_inputs'] or 0,
                'tool_call_count': row['agent_responses'] or 0,
                'error_count': row['errors'] or 0,
                'event_count': row['event_count']
            })

        return results

    except Exception as e:
        print(f"[ERROR] get_recent_sessions failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent events from Council Memory.

    Args:
        limit: Maximum number of events to return

    Returns:
        List of event dictionaries
    """
    if not COUNCIL_MEMORY_DB.exists():
        return []

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if events table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='events'
        """)
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("""
            SELECT
                event_id,
                timestamp,
                event_type,
                component,
                description,
                metadata,
                severity
            FROM events
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    except Exception as e:
        print(f"[ERROR] get_recent_events failed: {e}")
        return []


def get_decision_summary() -> Dict[str, Any]:
    """
    Get summary of system decisions from Council Memory.

    Returns:
        Dictionary with decision counts and recent decisions
    """
    if not COUNCIL_MEMORY_DB.exists():
        return {"error": "Council Memory database not found"}

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        cursor = conn.cursor()

        # Check if decisions table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='decisions'
        """)
        if not cursor.fetchone():
            conn.close()
            return {"decisions_count": 0, "recent": []}

        # Get count
        cursor.execute("SELECT COUNT(*) FROM decisions")
        count = cursor.fetchone()[0]

        # Get recent decisions
        cursor.execute("""
            SELECT
                decision_id,
                decision_type,
                decision_data,
                rationale,
                timestamp,
                is_active
            FROM decisions
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        rows = cursor.fetchall()
        conn.close()

        return {
            "decisions_count": count,
            "recent": [dict(row) for row in rows]
        }

    except Exception as e:
        return {"error": str(e)}


def get_constraint_summary() -> Dict[str, Any]:
    """
    Get summary of core constraints from Council Memory.

    Returns:
        Dictionary with constraint counts and active constraints
    """
    if not COUNCIL_MEMORY_DB.exists():
        return {"error": "Council Memory database not found"}

    try:
        conn = sqlite3.connect(str(COUNCIL_MEMORY_DB), timeout=5)
        cursor = conn.cursor()

        # Check if constraints table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='constraints'
        """)
        if not cursor.fetchone():
            conn.close()
            return {"constraints_count": 0, "active": []}

        # Get count
        cursor.execute("SELECT COUNT(*) FROM constraints WHERE is_active = 1")
        count = cursor.fetchone()[0]

        # Get active constraints
        cursor.execute("""
            SELECT
                constraint_id,
                constraint_type,
                description,
                severity,
                created_at
            FROM constraints
            WHERE is_active = 1
            ORDER BY severity DESC, created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return {
            "constraints_count": count,
            "active": [dict(row) for row in rows]
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# MAIN API FUNCTIONS
# ============================================================================

def handle_council_memory_request(query_params: dict) -> Dict[str, Any]:
    """
    Handle /api/council-memory endpoint request.

    Args:
        query_params: Query string parameters (limit, sections, etc.)

    Returns:
        Dictionary with stats, insights, sessions, events
    """
    limit = int(query_params.get("limit", [20])[0])

    # Handle sections parameter - can be comma-separated string or list
    sections_param = query_params.get("sections", ["stats", "insights", "sessions"])
    if isinstance(sections_param, list):
        # Join list elements and split by comma
        sections = ','.join(sections_param).split(',')
    else:
        sections = sections_param.split(',')

    result = {"timestamp": datetime.now().isoformat()}

    if "stats" in sections:
        result["stats"] = get_memory_stats()

    if "atomic_facts" in sections:
        result["atomic_facts"] = get_recent_atomic_facts(limit)

    if "insights" in sections:
        result["insights"] = get_recent_insights(limit)

    if "sessions" in sections:
        result["sessions"] = get_recent_sessions(limit)

    if "events" in sections:
        result["events"] = get_recent_events(limit)

    if "decisions" in sections:
        result["decisions"] = get_decision_summary()

    if "constraints" in sections:
        result["constraints"] = get_constraint_summary()

    return result


def handle_council_sessions_request(query_params: dict) -> Dict[str, Any]:
    """
    Handle /api/council-sessions endpoint request.

    Args:
        query_params: Query string parameters (limit)

    Returns:
        Dictionary with sessions list
    """
    limit = int(query_params.get("limit", [10])[0])

    return {
        "sessions": get_recent_sessions(limit),
        "count": len(get_recent_sessions(limit)),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    # Test the API
    print("Council Memory API Test")
    print("=" * 50)

    print("\n1. Memory Stats:")
    stats = get_memory_stats()
    print(json.dumps(stats, indent=2, default=str))

    print("\n2. Recent Insights (5):")
    insights = get_recent_insights(5)
    for insight in insights:
        print(f"  - [{insight.get('category', 'N/A')}] {insight.get('content', 'N/A')[:60]}...")

    print("\n3. Recent Sessions (3):")
    sessions = get_recent_sessions(3)
    for session in sessions:
        print(f"  - {session.get('session_id', 'N/A')}: {session.get('message_count', 0)} messages")

    print("\n4. API Request Test:")
    result = handle_council_memory_request({"limit": ["5"], "sections": ["stats", "insights"]})
    print(json.dumps(result, indent=2, default=str))
