#!/usr/bin/env python3
"""
pricing.py - Model pricing configuration for Council dashboard

Based on official provider pricing as of 2025-01-31
Prices are per 1M tokens (input/output)
"""

from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class ModelPricing:
    """Pricing information for a model."""
    input_price_per_1m: float  # USD per 1M input tokens
    output_price_per_1m: float  # USD per 1M output tokens
    provider: str


# Comprehensive pricing database
# Sources: Anthropic, Google DeepMind, DeepSeek, Moonshot AI
MODEL_PRICING: Dict[str, ModelPricing] = {
    # Claude Models (Anthropic)
    "claude-opus-4-5-20251101": ModelPricing(
        input_price_per_1m=15.0,
        output_price_per_1m=75.0,
        provider="anthropic"
    ),
    "claude-sonnet-4-20250514": ModelPricing(
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        provider="anthropic"
    ),
    "claude-haiku-4-20250514": ModelPricing(
        input_price_per_1m=0.80,
        output_price_per_1m=4.0,
        provider="anthropic"
    ),

    # Gemini Models (Google)
    "gemini-3-pro-preview": ModelPricing(
        input_price_per_1m=0,  # Free tier
        output_price_per_1m=0,
        provider="google"
    ),
    "gemini-2.0-flash": ModelPricing(
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
        provider="google"
    ),
    "gemini-2.0-flash-thinking": ModelPricing(
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
        provider="google"
    ),

    # DeepSeek Models
    "deepseek-chat": ModelPricing(
        input_price_per_1m=0.27,
        output_price_per_1m=1.10,
        provider="deepseek"
    ),
    "deepseek-reasoner": ModelPricing(
        input_price_per_1m=0.55,
        output_price_per_1m=2.19,
        provider="deepseek"
    ),

    # Kimi/Moonshot Models
    "kimi-k2-thinking-turbo": ModelPricing(
        input_price_per_1m=1.20,
        output_price_per_1m=12.0,
        provider="moonshot"
    ),
    "kimi-k2-thinking": ModelPricing(
        input_price_per_1m=1.20,
        output_price_per_1m=12.0,
        provider="moonshot"
    ),
    "kimi-k2.5": ModelPricing(
        input_price_per_1m=1.20,
        output_price_per_1m=12.0,
        provider="moonshot"
    ),

    # Gemini 2.0 Flash Experimental (used by architect, pro)
    "gemini-2.0-flash-exp": ModelPricing(
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
        provider="google"
    ),
}


# Council alias mapping (from models.py)
COUNCIL_MODEL_ALIASES = {
    "gemini-architect": "gemini-2.0-flash-exp",
    "gemini-flash": "gemini-2.0-flash",
    "gemini-flash-latest": "gemini-2.0-flash-exp",  # Points to Gemini API's experimental latest
    "gemini-flash-fallback": "gemini-2.0-flash",
    "gemini-3-pro-semifinal": "gemini-2.0-flash",
    "gemini-pro": "gemini-2.0-flash-exp",
    "gemini-pro-latest": "gemini-3-pro-preview",  # Points to Gemini API's latest preview
    "deepseek-v3": "deepseek-chat",
    "deepseek-security": "deepseek-reasoner",
    "kimi-researcher": "kimi-k2-thinking-turbo",
    "kimi-deep": "kimi-k2-thinking",
    "kimi-synthesis": "kimi-k2.5",
    "claude-sonnet": "claude-sonnet-4-20250514",
    "opus-synthesis": "claude-opus-4-5-20251101",
    # Perplexity models (search-based pricing, not token-based)
    "perplexity-online": "perplexity-online",
    "perplexity-researcher": "perplexity-researcher",
}


# ============================================================================
# PERPLEXITY SEARCH-BASED PRICING
# https://docs.perplexity.ai/docs/getting-started/overview
# Pricing is per search, not per token
# ============================================================================
PERPLEXITY_PRICING = {
    "perplexity-online": {
        "cost_per_search": 0.002,  # sonar-medium-online
        "provider": "perplexity",
    },
    "perplexity-researcher": {
        "cost_per_search": 0.001,  # sonar-small-online
        "provider": "perplexity",
    },
}


# ============================================================================
# TIER COST ESTIMATES (for budget prediction)
# ============================================================================
TIER_COSTS = {
    "tier_1": {
        "models": ["claude-sonnet"],
        "estimated_cost_range": (0.001, 0.005),
        "description": "Simple queries - Sonnet only",
        "typical_tokens": (500, 1500),
    },
    "tier_2": {
        "models": ["perplexity-researcher", "claude-sonnet"],
        "estimated_cost_range": (0.003, 0.010),
        "description": "Research queries - Perplexity + Sonnet",
        "typical_tokens": (1000, 3000),
    },
    "tier_3": {
        "models": ["kimi-researcher", "perplexity-online", "deepseek-v3", "gemini-flash", "claude-sonnet", "gemini-pro"],
        "estimated_cost_range": (0.10, 0.30),
        "description": "Full Diamond - all models",
        "typical_tokens": (15000, 40000),
    },
    "tier_3_lite": {
        "models": ["kimi-researcher", "deepseek-v3", "claude-sonnet", "gemini-pro"],
        "estimated_cost_range": (0.05, 0.15),
        "description": "Diamond Lite - reduced parallel models",
        "typical_tokens": (10000, 25000),
    },
}


def get_tier_estimate(tier_name: str) -> tuple[float, float]:
    """Get cost estimate range for a tier."""
    if tier_name not in TIER_COSTS:
        raise ValueError(f"Unknown tier: {tier_name}")
    return TIER_COSTS[tier_name]["estimated_cost_range"]


def get_pricing(model_alias: str) -> ModelPricing:
    """
    Get pricing for a Council model alias.

    Args:
        model_alias: Council model name (e.g., "gemini-architect")

    Returns:
        ModelPricing object for this model

    Raises:
        KeyError: If model alias not found
    """
    # Check if this is a Perplexity model (search-based pricing)
    if model_alias in PERPLEXITY_PRICING:
        # Return a special ModelPricing for search-based models
        # cost_per_search is stored in input_price_per_1m for convenience
        return ModelPricing(
            input_price_per_1m=PERPLEXITY_PRICING[model_alias]["cost_per_search"],
            output_price_per_1m=0,
            provider="perplexity"
        )

    # Resolve alias to underlying model
    underlying_model = COUNCIL_MODEL_ALIASES.get(model_alias, model_alias)

    # Get pricing
    if underlying_model not in MODEL_PRICING:
        # Default pricing for unknown models (conservative estimate)
        return ModelPricing(
            input_price_per_1m=1.0,
            output_price_per_1m=5.0,
            provider="unknown"
        )

    return MODEL_PRICING[underlying_model]


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> float:
    """
    Calculate API call cost in USD.

    Args:
        model: Council model alias
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens

    Returns:
        Cost in USD (rounded to 6 decimal places)
    """
    pricing = get_pricing(model)

    input_cost = (prompt_tokens / 1_000_000) * pricing.input_price_per_1m
    output_cost = (completion_tokens / 1_000_000) * pricing.output_price_per_1m

    return round(input_cost + output_cost, 6)


def estimate_max_cost(model: str, max_tokens: int) -> float:
    """
    Estimate maximum cost for a request (all tokens as output).

    Args:
        model: Council model alias
        max_tokens: Maximum tokens to generate

    Returns:
        Estimated maximum cost in USD
    """
    pricing = get_pricing(model)
    return round((max_tokens / 1_000_000) * pricing.output_price_per_1m, 6)


if __name__ == "__main__":
    # Test pricing calculations
    print("=== Council Model Pricing ===\n")

    test_cases = [
        ("gemini-architect", 1000, 500),
        ("deepseek-v3", 5000, 2000),
        ("opus-synthesis", 10000, 5000),
        ("kimi-synthesis", 3000, 1500),
    ]

    for model, prompt, completion in test_cases:
        cost = calculate_cost(model, prompt, completion)
        total = prompt + completion
        print(f"{model:20} | {total:6} tokens | ${cost:.6f}")

    print("\n=== Per-1M Token Prices ===")
    for alias in COUNCIL_MODEL_ALIASES:
        pricing = get_pricing(alias)
        print(f"{alias:20} | In: ${pricing.input_price_per_1m:.2f}/M | Out: ${pricing.output_price_per_1m:.2f}/M")
