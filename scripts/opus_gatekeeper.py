#!/usr/bin/env python3
"""
Opus Gatekeeper - Conditional Opus Invocation per Council Ruling

Implements Council v2.0 Phase 1 requirement: Conditional Opus invocation
to control costs while ensuring quality for critical decisions.

Per Council Ruling (2026-01-30):
- MANDATORY: strategy, architecture, client_communication, executive
- SKIP: code_implementation, simple_debugging, syntax_error
- Budget Gate: 40% of monthly budget
- Tier-Based: Tier 3 gets Opus by default
"""

import os
import sys
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from skills.council.scripts.models import (
        classify_query_tier,
        OPUS_MANDATORY_CATEGORIES,
        OPUS_SKIP_CATEGORIES,
        TIER_CONFIG,
    )
except ImportError:
    # Fallback definitions
    OPUS_MANDATORY_CATEGORIES = ["strategy", "architecture", "client_communication", "executive"]
    OPUS_SKIP_CATEGORIES = ["code_implementation", "simple_debugging", "syntax_error"]

    def classify_query_tier(query: str, token_count: int = 0, metadata: dict = None) -> str:
        return "tier_1"

    TIER_CONFIG = {}


class OpusDecision(Enum):
    """Opus invocation decision."""
    INVOKE = "INVOKE"  # Invoke Opus (mandatory or recommended)
    SKIP = "SKIP"  # Skip Opus (not needed)
    BUDGET_BLOCK = "BUDGET_BLOCK"  # Skip due to budget constraints


@dataclass
class GatekeeperResult:
    """Result from Opus gatekeeper analysis."""
    decision: OpusDecision
    reason: str
    confidence: float  # 0.0 - 1.0
    category: str  # MANDATORY, SKIP, or NONE
    tier: str
    budget_remaining: float
    budget_threshold: float


class OpusGatekeeper:
    """
    Gatekeeper for conditional Opus invocation.

    Enforces Council's cost-control measures while ensuring Opus
    is used for critical decisions.
    """

    # Budget gate threshold (40% of monthly budget)
    BUDGET_GATE_THRESHOLD = 0.40  # 40%

    # Minimum budget for Opus invocation
    MIN_OPUS_BUDGET = 0.50  # $0.50 minimum remaining

    # Keywords for category detection
    MANDATORY_KEYWORDS = {
        "strategy": [
            "strategy", "strategic", "roadmap", "vision", "long-term",
            "architecture decision", "system design", "tech stack choice",
            "should we", "which approach", "evaluate options", "compare",
        ],
        "architecture": [
            "architecture", "design", "refactor", "restructure", "pattern",
            "system", "module", "component", "integration", "api design",
            "database design", "schema", "workflow", "pipeline",
        ],
        "client_communication": [
            "client", "customer", "stakeholder", "presentation", "proposal",
            "explain to", "communicate", "report", "executive summary",
        ],
        "executive": [
            "executive", "leadership", "decision", "approve", "authorize",
            "budget", "timeline", "resource allocation", "priority",
        ],
    }

    SKIP_KEYWORDS = {
        "code_implementation": [
            "implement this", "write code", "create function", "add method",
            "implement", "build this", "code this",
        ],
        "simple_debugging": [
            "fix this bug", "debug", "error in", "not working",
            "throws error", "fails", "broken",
        ],
        "syntax_error": [
            "syntax error", "parse error", "indentation", "missing",
            "unexpected token", "invalid syntax",
        ],
    }

    def __init__(
        self,
        monthly_budget: float = 100.0,
        current_monthly_spend: float = 0.0,
        budget_threshold: float = BUDGET_GATE_THRESHOLD
    ):
        """
        Initialize the Opus gatekeeper.

        Args:
            monthly_budget: Total monthly budget (default: $100)
            current_monthly_spend: Amount already spent this month
            budget_threshold: Budget gate threshold (default: 40%)
        """
        self.monthly_budget = monthly_budget
        self.current_monthly_spend = current_monthly_spend
        self.budget_threshold = budget_threshold

        # Calculate budget gate
        self.budget_gate = monthly_budget * budget_threshold

    def _classify_category(self, query: str) -> Tuple[str, float]:
        """
        Classify query into MANDATORY, SKIP, or NONE category.

        Args:
            query: The user's query

        Returns:
            Tuple of (category, confidence)
        """
        query_lower = query.lower()

        # Check MANDATORY categories
        for category, keywords in self.MANDATORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    return f"MANDATORY:{category}", 0.9

        # Check SKIP categories
        for category, keywords in self.SKIP_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    return f"SKIP:{category}", 0.9

        return "NONE", 0.5

    def _check_budget(self) -> Tuple[bool, float]:
        """
        Check if budget allows Opus invocation.

        Returns:
            Tuple of (can_invoke, remaining_budget)
        """
        remaining = self.monthly_budget - self.current_monthly_spend
        can_invoke = remaining >= self.MIN_OPUS_BUDGET

        return can_invoke, remaining

    def _check_tier_eligibility(self, tier: str) -> bool:
        """
        Check if tier is eligible for Opus.

        Args:
            tier: Tier classification

        Returns:
            True if tier gets Opus by default
        """
        # Tier 3 (Full Council) gets Opus by default
        return tier == "tier_3"

    def should_invoke_opus(
        self,
        query: str,
        tier: str = None,
        token_count: int = 0,
        metadata: dict = None
    ) -> GatekeeperResult:
        """
        Determine if Opus should be invoked for this query.

        Args:
            query: The user's query
            tier: Pre-classified tier (will classify if not provided)
            token_count: Estimated token count
            metadata: Additional metadata

        Returns:
            GatekeeperResult with decision and rationale
        """
        # Classify tier if not provided
        if tier is None:
            tier = classify_query_tier(query, token_count, metadata)

        # Classify category
        category, confidence = self._classify_category(query)

        # Check budget
        can_invoke_budget, remaining = self._check_budget()

        # Decision logic (per Council ruling)

        # 1. MANDATORY categories always invoke Opus (if budget allows)
        if category.startswith("MANDATORY:"):
            if can_invoke_budget:
                return GatekeeperResult(
                    decision=OpusDecision.INVOKE,
                    reason=f"MANDATORY category ({category.split(':', 1)[1]}) per Council ruling",
                    confidence=confidence,
                    category=category,
                    tier=tier,
                    budget_remaining=remaining,
                    budget_threshold=self.budget_gate,
                )
            else:
                return GatekeeperResult(
                    decision=OpusDecision.BUDGET_BLOCK,
                    reason=f"MANDATORY category but budget insufficient (${remaining:.2f} < ${self.MIN_OPUS_BUDGET})",
                    confidence=1.0,
                    category=category,
                    tier=tier,
                    budget_remaining=remaining,
                    budget_threshold=self.budget_gate,
                )

        # 2. SKIP categories never invoke Opus
        if category.startswith("SKIP:"):
            return GatekeeperResult(
                decision=OpusDecision.SKIP,
                reason=f"SKIP category ({category.split(':', 1)[1]}) per Council ruling",
                confidence=confidence,
                category=category,
                tier=tier,
                budget_remaining=remaining,
                budget_threshold=self.budget_gate,
            )

        # 3. Budget gate check (40% threshold)
        if self.current_monthly_spend > self.budget_gate:
            # Above budget gate, skip non-mandatory Opus
            return GatekeeperResult(
                decision=OpusDecision.BUDGET_BLOCK,
                reason=f"Budget gate exceeded (${self.current_monthly_spend:.2f} > ${self.budget_gate:.2f})",
                confidence=0.8,
                category=category,
                tier=tier,
                budget_remaining=remaining,
                budget_threshold=self.budget_gate,
            )

        # 4. Tier-based eligibility
        if self._check_tier_eligibility(tier):
            if can_invoke_budget:
                return GatekeeperResult(
                    decision=OpusDecision.INVOKE,
                    reason=f"Tier {tier} invokes Opus by default",
                    confidence=0.7,
                    category=category,
                    tier=tier,
                    budget_remaining=remaining,
                    budget_threshold=self.budget_gate,
                )
            else:
                return GatekeeperResult(
                    decision=OpusDecision.BUDGET_BLOCK,
                    reason=f"Tier {tier} eligible but budget insufficient",
                    confidence=0.7,
                    category=category,
                    tier=tier,
                    budget_remaining=remaining,
                    budget_threshold=self.budget_gate,
                )

        # 5. Default: Skip Opus for simple queries
        return GatekeeperResult(
            decision=OpusDecision.SKIP,
            reason=f"No mandatory category detected, Tier {tier} does not require Opus",
            confidence=0.6,
            category=category,
            tier=tier,
            budget_remaining=remaining,
            budget_threshold=self.budget_gate,
        )

    def recommend_degradation(self, result: GatekeeperResult) -> Optional[str]:
        """
        Recommend alternative if Opus cannot be invoked.

        Args:
            result: The gatekeeper result

        Returns:
            Recommended alternative model or None
        """
        if result.decision == OpusDecision.INVOKE:
            return None

        if result.decision == OpusDecision.BUDGET_BLOCK:
            # Budget issue: degrade to cheaper synthesizer
            return "gemini-pro"

        if result.decision == OpusDecision.SKIP and result.tier == "tier_3":
            # Explicit skip in Tier 3: use gemini-pro instead
            return "gemini-pro"

        return None


# ============================================================================
# CLI Testing
# ============================================================================
if __name__ == "__main__":
    import json

    gatekeeper = OpusGatekeeper(monthly_budget=100.0, current_monthly_spend=30.0)

    print("=== Opus Gatekeeper Test ===\n")

    test_queries = [
        ("design a new auth system architecture", "tier_3"),
        ("fix this syntax error in my code", "tier_1"),
        ("what is the best strategy for user retention", "tier_2"),
        ("implement a login function", "tier_1"),
        ("create a presentation for client stakeholders", "tier_2"),
        ("should we use PostgreSQL or MongoDB", "tier_3"),
    ]

    for query, expected_tier in test_queries:
        result = gatekeeper.should_invoke_opus(query, tier=expected_tier)

        print(f"Query: {query}")
        print(f"  Tier: {result.tier}")
        print(f"  Decision: {result.decision.value}")
        print(f"  Category: {result.category}")
        print(f"  Reason: {result.reason}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Budget Remaining: ${result.budget_remaining:.2f}")

        if result.decision != OpusDecision.INVOKE:
            alternative = gatekeeper.recommend_degradation(result)
            if alternative:
                print(f"  → Alternative: {alternative}")

        print()
