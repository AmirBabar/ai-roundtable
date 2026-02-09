#!/usr/bin/env python3
"""
Diamond Cost Predictor - Pre-flight budget estimation and reservation

Implements Council v2.0 requirement: Pre-flight budget reservation
to prevent unbounded cost exposure.

Per Council Ruling:
- No single query may exceed $2.50 in API costs
- Budget must be reserved before parallel dispatch
- Failure triggers automatic degradation to Tier 1
"""

import sys
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from dashboard.backend.pricing import (
        calculate_cost,
        get_pricing,
        MODEL_PRICING,
        TIER_COSTS,
        COUNCIL_MODEL_ALIASES,
    )
except ImportError:
    # Fallback if dashboard not in path
    MODEL_PRICING = {}
    TIER_COSTS = {}
    COUNCIL_MODEL_ALIASES = {}


@dataclass
class CostEstimate:
    """Cost estimate for a query."""
    tier: str
    models: List[str]
    estimated_min_cost: float
    estimated_max_cost: float
    estimated_tokens: int
    can_proceed: bool
    reason: str


@dataclass
class TokenEstimate:
    """Token count estimate for a query."""
    input_tokens: int
    output_per_model: Dict[str, int]  # Expected output per model


class DiamondCostPredictor:
    """
    Pre-flight cost estimator and budget reservation system.

    Per Council Phase 0 requirement: Must estimate cost before execution
    and enforce $2.50 per-query ceiling.
    """

    # Per-query cost ceiling (Council ruling)
    MAX_COST_PER_QUERY = 2.50

    # Token estimation rules (conservative estimates)
    AVG_INPUT_TOKENS_PER_CHAR = 0.25  # ~4 chars per token
    AVG_OUTPUT_TOKENS_PER_INPUT = 0.5  # Output is typically 50% of input

    # Per-model output token limits (Council requirement)
    MAX_OUTPUT_TOKENS_PER_MODEL = 2000

    def __init__(self, monthly_budget: float = 100.0, current_monthly_spend: float = 0.0):
        """
        Initialize the cost predictor.

        Args:
            monthly_budget: Total monthly budget (default: $100)
            current_monthly_spend: Amount already spent this month
        """
        self.monthly_budget = monthly_budget
        self.current_monthly_spend = current_monthly_spend

        # Budget allocation by tier (percentage of monthly budget)
        self.tier_budget_allocation = {
            "tier_1": 0.20,  # 20% for simple queries
            "tier_2": 0.40,  # 40% for research queries
            "tier_3": 0.40,  # 40% for full Council (carefully allocated)
        }

    def estimate_tokens(self, query: str, context: str = "") -> TokenEstimate:
        """
        Estimate token counts for a query.

        Args:
            query: The user's query
            context: Additional context (file contents, etc.)

        Returns:
            TokenEstimate with input and expected output per model
        """
        # Estimate input tokens
        input_text = query + "\n" + context
        input_tokens = int(len(input_text) * self.AVG_INPUT_TOKENS_PER_CHAR)

        # Estimate output tokens per model (conservative 50% of input)
        # Use MAX_OUTPUT_TOKENS_PER_MODEL as upper bound
        estimated_base_output = int(input_tokens * self.AVG_OUTPUT_TOKENS_PER_INPUT)

        # Per-model limits
        output_per_model = {
            "claude-sonnet": min(estimated_base_output, 2000),
            "deepseek-v3": min(estimated_base_output * 0.8, 2000),
            "gemini-flash": min(estimated_base_output * 0.5, 1000),
            "kimi-researcher": min(estimated_base_output * 1.5, 2000),
            "gemini-pro": min(estimated_base_output * 2.0, 5000),  # Synthesizer needs more
            "opus-synthesis": min(estimated_base_output * 1.5, 4000),
            "perplexity-online": 500,  # Search results are typically longer
            "perplexity-researcher": 300,
        }

        return TokenEstimate(
            input_tokens=input_tokens,
            output_per_model=output_per_model,
        )

    def estimate_tier_cost(
        self,
        tier: str,
        models: List[str],
        input_tokens: int,
        output_per_model: Dict[str, int]
    ) -> Tuple[float, float]:
        """
        Estimate min and max cost for a tier execution.

        Args:
            tier: Tier name
            models: List of model names
            input_tokens: Input token count
            output_per_model: Expected output tokens per model

        Returns:
            Tuple of (min_cost, max_cost)
        """
        min_cost = 0.0
        max_cost = 0.0

        for model in models:
            try:
                output_tokens = output_per_model.get(model, 1000)  # Default fallback

                # Handle Perplexity search-based pricing
                if model in ["perplexity-online", "perplexity-researcher"]:
                    from dashboard.backend.pricing import PERPLEXITY_PRICING
                    cost = PERPLEXITY_PRICING[model]["cost_per_search"]
                    min_cost += cost
                    max_cost += cost
                else:
                    cost = calculate_cost(model, input_tokens, output_tokens)
                    min_cost += cost
                    max_cost += cost
            except (KeyError, Exception):
                # Unknown model - use conservative estimate
                min_cost += 0.01
                max_cost += 0.05

        return round(min_cost, 4), round(max_cost, 4)

    def check_budget_reservation(
        self,
        tier: str,
        estimated_cost: float
    ) -> Tuple[bool, str]:
        """
        Check if budget can be reserved for this query.

        Args:
            tier: Tier name
            estimated_cost: Estimated maximum cost

        Returns:
            Tuple of (can_proceed, reason)
        """
        # Check per-query ceiling (Council ruling)
        if estimated_cost > self.MAX_COST_PER_QUERY:
            return False, f"Cost ${estimated_cost:.2f} exceeds per-query ceiling of ${self.MAX_COST_PER_QUERY}"

        # Check monthly budget
        remaining_budget = self.monthly_budget - self.current_monthly_spend

        if estimated_cost > remaining_budget:
            return False, f"Insufficient budget: ${estimated_cost:.2f} > ${remaining_budget:.2f} remaining"

        # Check tier budget allocation
        tier_budget = self.monthly_budget * self.tier_budget_allocation.get(tier, 0.20)
        tier_spend = self.current_monthly_spend * self.tier_budget_allocation.get(tier, 0.20)

        if estimated_cost > (tier_budget - tier_spend):
            return False, f"Tier budget exceeded: ${estimated_cost:.2f} > ${tier_budget - tier_spend:.2f} tier budget remaining"

        return True, "Budget available"

    def predict_and_reserve(
        self,
        query: str,
        context: str = "",
        tier: str = "tier_1",
        models: Optional[List[str]] = None
    ) -> CostEstimate:
        """
        Full cost prediction and budget reservation.

        Args:
            query: User's query
            context: Additional context (file contents, etc.)
            tier: Tier classification
            models: Optional list of models (defaults to tier's models)

        Returns:
            CostEstimate with prediction results
        """
        # Use tier's default models if not specified
        if models is None:
            from skills.council.scripts.models import get_models_for_tier
            try:
                models = get_models_for_tier(tier)
            except:
                models = ["claude-sonnet"]  # Fallback

        # Estimate tokens
        token_estimate = self.estimate_tokens(query, context)

        # Estimate cost range
        min_cost, max_cost = self.estimate_tier_cost(tier, models, token_estimate.input_tokens, token_estimate.output_per_model)

        # Check budget
        can_proceed, reason = self.check_budget_reservation(tier, max_cost)

        return CostEstimate(
            tier=tier,
            models=models,
            estimated_min_cost=min_cost,
            estimated_max_cost=max_cost,
            estimated_tokens=token_estimate.input_tokens,
            can_proceed=can_proceed,
            reason=reason
        )

    def recommend_degradation(self, cost_estimate: CostEstimate) -> str:
        """
        Recommend a degraded tier if the primary tier cannot proceed.

        Args:
            cost_estimate: The failed cost estimate

        Returns:
            Recommended tier to use instead
        """
        if cost_estimate.tier == "tier_3":
            if "budget" in cost_estimate.reason.lower():
                return "tier_1"  # Skip to cheapest if budget issue
            return "tier_3_lite"  # Use lite version otherwise

        if cost_estimate.tier == "tier_2":
            return "tier_1"  # Only one degradation level

        return cost_estimate.tier  # No degradation available


# ============================================================================
# CLI Testing
# ============================================================================
if __name__ == "__main__":
    predictor = DiamondCostPredictor(monthly_budget=100.0)

    print("=== Diamond Cost Predictor Test ===\n")

    test_queries = [
        ("fix this syntax error", "tier_1"),
        ("what is the latest claude opus pricing", "tier_2"),
        ("@council_v2 design a new auth system architecture", "tier_3"),
    ]

    for query, tier in test_queries:
        print(f"Query: {query}")
        print(f"  Tier: {tier}")

        estimate = predictor.predict_and_reserve(query, tier=tier)

        print(f"  Models: {estimate.models}")
        print(f"  Cost: ${estimate.estimated_min_cost:.4f} - ${estimate.estimated_max_cost:.4f}")
        print(f"  Tokens: ~{estimate.estimated_tokens}")
        print(f"  Can Proceed: {estimate.can_proceed}")
        print(f"  Reason: {estimate.reason}")

        if not estimate.can_proceed:
            recommended = predictor.recommend_degradation(estimate)
            print(f"  → Recommend: {recommended}")

        print()
