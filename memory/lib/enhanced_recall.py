#!/usr/bin/env python3
"""
enhanced_recall.py - Enhanced Context Recall with Shadow Fact Support

Per Council Decree 2024-COUNCIL-MEM-001, Phase 3.1:
"The Court ORDERS that recall_context() remain largely unchanged.
The only modification is to add shadow fact inclusion under severe recall failure."

Key Features:
1. TokenBudgetAllocator for dynamic budget management
2. Shadow fact fallback at <10% utilization
3. SemanticDeduplicator to prevent echo effect
4. Backward compatible with existing recall_context()
"""

import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class TokenBudgetAllocator:
    """
    Dynamic token budget allocation for hybrid recall.

    Per decree: "Use TokenBudgetAllocator class (proven pattern)"
    """

    def __init__(
        self,
        total_budget: int = 8000,
        safety_margin: int = 500,
        fact_weight: float = 0.7,
        shadow_weight: float = 0.3
    ):
        self.total_budget = total_budget - safety_margin
        self.fact_weight = fact_weight
        self.shadow_weight = shadow_weight

    def get_fact_budget(self) -> int:
        """Get token budget for active facts."""
        return int(self.total_budget * self.fact_weight)

    def get_shadow_budget(self, used_tokens: int) -> int:
        """Get remaining budget for shadow facts."""
        return max(0, self.total_budget - used_tokens)

    def calculate_utilization(self, used_tokens: int) -> float:
        """Calculate utilization percentage."""
        return used_tokens / self.get_fact_budget() if self.get_fact_budget() > 0 else 1.0


class SemanticDeduplicator:
    """
    Prevent echo effect by detecting duplicate facts.

    Per decree: "Mandatory: SemanticDeduplicator on combined fact+event list"
    """

    def __init__(self, similarity_threshold: float = 0.95):
        self.similarity_threshold = similarity_threshold

    def collapse(self, items: List[Dict]) -> List[Dict]:
        """
        Remove semantically duplicate items from combined list.

        Simple implementation based on content similarity.
        Production would use embedding-based similarity.
        """
        if not items:
            return []

        # Track seen content
        seen = set()
        deduped = []

        for item in items:
            content = item.get('content', '')

            # Simple hash-based deduplication
            content_hash = hash(content.lower().strip())

            if content_hash not in seen:
                seen.add(content_hash)
                deduped.append(item)

        return deduped


def recall_context_enhanced(
    db_path: Path,
    query: str = "",
    fact_limit: int = 20,
    include_shadow_on_low_utilization: bool = True,
    utilization_threshold: float = 0.10
) -> Dict[str, Any]:
    """
    Enhanced context recall with shadow fact fallback.

    Per Council Decree Phase 3.1:
    1. Retrieve atomic facts (existing logic)
    2. Calculate utilization
    3. EMERGENCY FALLBACK: Include shadow + recent raw if severe gap

    Args:
        db_path: Path to database
        query: Optional query for semantic search (future use)
        fact_limit: Maximum facts to retrieve
        include_shadow_on_low_utilization: Enable shadow fallback
        utilization_threshold: Threshold for shadow fallback (default: 10%)

    Returns:
        Dictionary with facts, utilization, shadow_used flag
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Initialize allocator
        allocator = TokenBudgetAllocator(total_budget=8000)

        # Step 1: Retrieve active atomic facts (exclude shadow)
        cursor.execute("""
            SELECT fact_id, content, category, confidence,
                   first_observed, observation_count
            FROM atomic_facts
            WHERE is_active = 1 AND (is_shadow IS NULL OR is_shadow = 0)
            ORDER BY last_confirmed DESC
            LIMIT ?
        """, (fact_limit,))

        facts = [dict(row) for row in cursor.fetchall()]

        # Calculate token usage (rough estimate: 1 token ~ 4 chars)
        fact_tokens = sum(len(f.get('content', '')) // 4 for f in facts)
        utilization = allocator.calculate_utilization(fact_tokens)

        # Step 2: Check if shadow fallback needed
        shadow_facts = []
        used_shadow_fallback = False

        if include_shadow_on_low_utilization and utilization < utilization_threshold:
            # EMERGENCY FALLBACK: Include shadow facts
            remaining_budget = allocator.get_shadow_budget(fact_tokens)
            shadow_limit = remaining_budget // 200  # Rough estimate

            cursor.execute("""
                SELECT fact_id, content, category, confidence,
                       first_observed, observation_count
                FROM atomic_facts
                WHERE is_active = 1 AND is_shadow = 1
                ORDER BY last_confirmed DESC
                LIMIT ?
            """, (shadow_limit,))

            shadow_facts = [dict(row) for row in cursor.fetchall()]
            used_shadow_fallback = len(shadow_facts) > 0

        # Step 3: Deduplicate (MANDATORY per decree)
        deduplicator = SemanticDeduplicator()
        combined = deduplicator.collapse(facts + shadow_facts)

        # Build context string
        context = _build_context_string(combined)

        # Add metadata
        result = {
            'success': True,
            'context': context,
            'facts': combined,
            'active_fact_count': len(facts),
            'shadow_fact_count': len(shadow_facts),
            'total_fact_count': len(combined),
            'utilization': round(utilization, 2),
            'used_shadow_fallback': used_shadow_fallback,
            'error': None
        }

        return result

    except Exception as e:
        return {
            'success': False,
            'context': '',
            'facts': [],
            'active_fact_count': 0,
            'shadow_fact_count': 0,
            'total_fact_count': 0,
            'utilization': 0,
            'used_shadow_fallback': False,
            'error': str(e)
        }

    finally:
        conn.close()


def _build_context_string(facts: List[Dict]) -> str:
    """Build formatted context string from facts list."""
    if not facts:
        return "# Council Memory Context\n\nNo facts available."

    lines = ["# Council Memory Context\n"]

    # Group by category
    by_category = {}
    for fact in facts:
        cat = fact.get('category', 'unknown')
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(fact)

    # Add Layer 1 facts
    lines.append("## Layer 1: Atomic Facts\n")
    lines.append(f"Retrieved {len(facts)} facts at {datetime.now().isoformat()}\n")

    for category, cat_facts in sorted(by_category.items()):
        lines.append(f"\n### {category.replace('_', ' ').title()}\n")
        for fact in cat_facts:
            shadow_tag = "[SHADOW] " if fact.get('is_shadow') else ""
            lines.append(f"- {shadow_tag}{fact['content']}")
            if fact.get('confidence') and fact['confidence'] < 0.8:
                lines.append(f"  (confidence: {fact['confidence']})")

    return "\n".join(lines)


def recall_with_recent_events(
    db_path: Path,
    query: str = "",
    fact_limit: int = 15,
    recent_event_limit: int = 5
) -> Dict[str, Any]:
    """
    Recall context with recent unpromoted events included.

    Alternative recall strategy that includes recent events
    even if not yet promoted to facts.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get atomic facts
        result = recall_context_enhanced(db_path, query, fact_limit)

        if not result['success']:
            return result

        # Get recent pending events
        cursor.execute("""
            SELECT e.id, e.event_type, e.content, e.created_at
            FROM events e
            INNER JOIN event_promotion_state eps ON e.id = eps.event_id
            WHERE eps.processing_status = 'pending'
            ORDER BY e.id DESC
            LIMIT ?
        """, (recent_event_limit,))

        recent_events = [dict(row) for row in cursor.fetchall()]

        if recent_events:
            # Add recent events to context
            lines = [result['context'], "\n## Recent Unprocessed Events\n"]
            for event in recent_events:
                lines.append(f"\n[Event {event['id']}] {event['event_type']}: {event['content'][:200]}...")

            result['context'] = "\n".join(lines)
            result['recent_event_count'] = len(recent_events)

        return result

    finally:
        conn.close()


# Backward compatible wrapper for existing memory_bridge.py
def recall_context_legacy(
    session_id: Optional[str] = None,
    category_filter: str = "",
    fact_limit: int = 20
) -> Dict[str, Any]:
    """
    Legacy wrapper for backward compatibility.

    Maintains the same interface as the original recall_context()
    but uses enhanced implementation.
    """
    db_path = Path.home() / '.claude' / 'memory' / 'data' / 'council_memory.db'

    result = recall_context_enhanced(
        db_path=db_path,
        query=category_filter,
        fact_limit=fact_limit
    )

    # Map to legacy format
    return {
        'success': result['success'],
        'context': result['context'],
        'summaries': [],  # Layer 2 not implemented yet
        'facts': result['facts'],
        'error': result['error']
    }


if __name__ == '__main__':
    # Test the enhanced recall
    db_path = Path.home() / '.claude' / 'memory' / 'data' / 'council_memory.db'

    print("=== ENHANCED RECALL TEST ===\n")

    result = recall_context_enhanced(db_path)

    if result['success']:
        print(result['context'])
        print(f"\n--- Statistics ---")
        print(f"Active facts: {result['active_fact_count']}")
        print(f"Shadow facts: {result['shadow_fact_count']}")
        print(f"Utilization: {result['utilization']*100}%")
        print(f"Shadow fallback used: {result['used_shadow_fallback']}")
    else:
        print(f"Error: {result['error']}")
