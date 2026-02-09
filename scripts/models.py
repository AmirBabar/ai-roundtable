#!/usr/bin/env python3
"""
models.py - Model configurations for Council system

Addresses Council Blocker: Model selection, proper tier assignment
"""

# Model configurations for each mode
BRAINSTORMING_MODELS = {
    "models": [
        {"id": "kimi-researcher", "name": "Kimi K2 Thinking", "timeout": 60},  # Cost-effective with thinking
        {"id": "deepseek-v3", "name": "DeepSeek V3", "timeout": 60},
        {"id": "gemini-flash", "name": "Gemini Flash", "timeout": 60},  # Fast ideation
    ],
    "synthesizer": {"id": "claude-sonnet", "name": "Claude Sonnet", "timeout": 90},
    "parallel": True,
    "max_ideas": 20,
}

# REVISED per Council: Remove Flash from refinement chain
REFINEMENT_MODELS = {
    "rounds": [
        {"model": "kimi-synthesis", "role": "Draft and initial review", "timeout": 90},
        {"model": "claude-sonnet", "role": "Critique, expand, and improve", "timeout": 180},
        {"model": "opus-synthesis", "role": "Final polish and approval", "timeout": 180},
    ],
    "sequential": True,
    "rollback_enabled": True,  # Addresses Council Blocker: No rollback mechanism
}

BUILD_PLANNING_MODELS = {
    "rounds": [
        {
            "model": "kimi-researcher",  # Tier 3: Cost-effective initial architecture
            "role": "Cost Architect",
            "timeout": 120,
            "instructions": [
                "Analyze cost-benefit of proposed approach",
                "Design system architecture",
                "Identify key components",
                "Define API contracts",
                "Consider system compatibility (Windows/Linux/Mac)",
                "Prioritize cost-effective solutions",
                "Consider security implications",
            ]
        },
        {
            "model": "deepseek-v3",
            "role": "Auditor - CRITICAL REVIEW",
            "timeout": 180,
            "instructions": [
                "CRITICAL REVIEW - Identify BLOCKER issues:",
                "Security risks (PII, SQL injection, XSS, credentials)",
                "Compatibility issues (Windows paths, encoding, Python versions)",
                "Technical risks (failure modes, bottlenecks)",
                "Missing components or dependencies",
                "What could go wrong?",
                "Cost concerns",
            ]
        },
        {
            "model": "claude-sonnet",
            "role": "Contextualist",
            "timeout": 180,
            "instructions": [
                "Check existing codebase patterns",
                "Identify integration points",
                "What can be reused?",
                "Dependencies and conflicts",
                "File structure implications",
            ]
        },
        {
            "model": "gemini-3-pro-semifinal",  # NEW: Semi-final synthesis before Opus
            "role": "Semi-Final Judge",
            "timeout": 180,
            "instructions": [
                "SEMI-FINAL SYNTHESIS - Incorporate all views:",
                "Review Cost Architect's proposal",
                "Consider Auditor's critiques",
                "Integrate Contextualist's codebase awareness",
                "Provide your own assessment of the approach",
                "Identify remaining concerns or gaps",
                "IMPORTANT: Do not filter out 'BLOCKER' warnings from the Auditor - highlight them prominently",
                "Recommend approval path:",
                "  - APPROVED (ready for Opus final review)",
                "  - CONDITIONAL (address X before Opus)",
                "  - NEEDS_DEBATE (major concerns remain)",
                "Prepare summary for Final Judge (Opus)",
            ]
        },
        {
            "model": "opus-synthesis",
            "role": "Final Judge",
            "timeout": 120,
            "instructions": [
                "FINAL DECISION REQUIRED:",
                "Review Semi-Final Judge's assessment",
                "Consider all previous perspectives",
                "Issue final decree:",
                "  - APPROVED (ready to build)",
                "  - CONDITIONAL (fix X first)",
                "  - REJECTED (not viable)",
                "Provide clear rationale",
                "Implementation phases",
                "Risks to mitigate",
                "Success criteria",
            ]
        },
    ],
    "sequential": True,
}

# Gateway configuration
GATEWAY_URL = "http://localhost:4000/v1/chat/completions"

# Model fallbacks (if primary fails) - Updated to match gateway config
MODEL_FALLBACKS = {
    "gemini-flash": "gemini-flash-fallback",
    "gemini-flash-latest": "gemini-flash",  # Falls back to stable gemini-flash
    "deepseek-v3": "gemini-flash",
    "kimi-researcher": "kimi-synthesis",
    "kimi-synthesis": "claude-sonnet",
    "kimi-deep": "kimi-synthesis",
    "claude-sonnet": "opus-synthesis",
    "opus-synthesis": "claude-sonnet",
    "gemini-architect": "gemini-flash",  # Falls back to gemini-flash for fast validation
    "gemini-3-pro-semifinal": "claude-sonnet",  # Fallback for semi-final judge
    "gemini-pro": "claude-sonnet",  # Fallback for synthesizer
    "gemini-pro-latest": "gemini-pro",  # Falls back to gemini-pro, then to sonnet
    # Perplexity models
    "perplexity-online": "gemini-flash",  # Fallback to internal model if search fails
    "perplexity-researcher": "gemini-flash",
}


# ============================================================================
# TIER CONFIGURATION (Council v2.0 Diamond Architecture)
# ============================================================================

TIER_CONFIG = {
    "tier_1": {
        "name": "Simple Query",
        "description": "Fast, single-model responses for straightforward questions",
        "models": ["claude-sonnet"],
        "triggers": {
            "no_arch_keywords": True,  # No architecture/strategy keywords
            "max_tokens": 500,          # Less than 500 tokens
            "single_file": True,         # Single file scope
        },
        "estimated_cost": (0.001, 0.005),  # $0.001 - $0.005
        "estimated_latency": 5,          # ~5 seconds
    },
    "tier_2": {
        "name": "Research Query",
        "description": "Web research + synthesis for external documentation",
        "models": ["perplexity-researcher", "claude-sonnet"],
        "triggers": {
            "has_docs_lookup": True,     # Requires external docs
            "has_research_tag": True,      # @research tag
            "external_api": True,          # API pricing/docs questions
        },
        "estimated_cost": (0.003, 0.010),  # $0.003 - $0.01
        "estimated_latency": 15,         # ~15 seconds
    },
    "tier_3": {
        "name": "Full Council (Diamond Architecture)",
        "description": "Complete parallel deliberation for architectural decisions",
        "models": [
            # Stage 1: Context Acquisition (Parallel)
            "kimi-researcher", "perplexity-online",
            # Stage 2: Deliberation (Parallel)
            "deepseek-v3", "gemini-flash", "claude-sonnet",
            # Stage 3: Synthesis
            "gemini-pro",
            # Stage 4: Ratification (conditional)
            "opus-synthesis",
        ],
        "triggers": {
            "has_council_v2_tag": True,     # @council_v2 explicit tag
            "is_architectural": True,       # Auto-classified as architectural
            "high_complexity": True,        # Complex, multi-file decisions
        },
        "estimated_cost": (0.10, 0.30),    # $0.10 - $0.30
        "estimated_latency": 45,         # ~45 seconds (parallel execution)
    },
    "tier_3_lite": {
        "name": "Diamond Lite",
        "description": "Reduced parallel deliberation for medium complexity",
        "models": ["kimi-researcher", "deepseek-v3", "claude-sonnet", "gemini-pro"],
        "triggers": {
            "has_council_lite_tag": True,    # @council_lite tag
            "medium_complexity": True,       # Medium complexity
        },
        "estimated_cost": (0.05, 0.15),     # $0.05 - $0.15
        "estimated_latency": 25,          # ~25 seconds
    },
}


# Keywords that trigger higher-tier processing
ARCHITECTURAL_KEYWORDS = [
    "architecture", "design", "refactor", "restructure",
    "system", "module", "component", "integration", "api design", "database design",
    "schema", "workflow", "pipeline", "strategy", "pattern",
    # Comparison keywords (choosing between options)
    " vs ", " versus ", " or ", " compare ", " which ", " should we use ",
    "microservices", "monolith", "postgresql", "mongodb", "mysql",
]

# Simple implementation keywords (Tier 1 - these take precedence)
SIMPLE_IMPLEMENTATION_KEYWORDS = [
    "implement a", "implement the", "create a", "create the",
    "write a", "write the", "add a", "add the",
    "fix this", "debug", "syntax error", "indentation",
]

EXTERNAL_DOCS_KEYWORDS = [
    "pricing", "latest version", "current docs", "documentation",
    "api reference", "changelog", "release notes", "official docs",
]

# Opus mandatory categories (per Council ruling)
OPUS_MANDATORY_CATEGORIES = [
    "strategy", "architecture", "client_communication", "executive",
]

# Opus skip categories (per Council ruling)
OPUS_SKIP_CATEGORIES = [
    "code_implementation", "simple_debugging", "syntax_error",
]


def classify_query_tier(query: str, token_count: int = 0, metadata: dict = None) -> str:
    """
    Classify a query into the appropriate tier.

    Args:
        query: The user's query
        token_count: Estimated token count (optional)
        metadata: Additional metadata (file count, etc.)

    Returns:
        Tier name: "tier_1", "tier_2", "tier_3", or "tier_3_lite"
    """
    metadata = metadata or {}
    query_lower = query.lower()

    # Check for explicit tags (highest priority)
    if "@council_v2" in query_lower:
        return "tier_3"
    if "@council_lite" in query_lower:
        return "tier_3_lite"
    if "@research" in query_lower:
        return "tier_2"

    # Check for simple implementation keywords (Tier 1 - takes precedence)
    has_simple_impl = any(kw in query_lower for kw in SIMPLE_IMPLEMENTATION_KEYWORDS)

    # Check for architectural keywords
    has_arch_keywords = any(kw in query_lower for kw in ARCHITECTURAL_KEYWORDS)

    # Check for external docs keywords
    has_docs_keywords = any(kw in query_lower for kw in EXTERNAL_DOCS_KEYWORDS)

    # Apply tier logic (simple implementation first, then docs, then architecture)
    if has_simple_impl:
        return "tier_1"

    if has_docs_keywords:
        return "tier_2"

    if has_arch_keywords:
        return "tier_3"

    # Default: Tier 1 for simple queries
    return "tier_1"


def should_invoke_opus(query: str, tier: str, current_monthly_spend: float = 0) -> bool:
    """
    Determine if Opus should be invoked for this query.

    Args:
        query: The user's query
        tier: The classified tier
        current_monthly_spend: Current Opus spend for the month

    Returns:
        True if Opus should be invoked, False otherwise
    """
    query_lower = query.lower()

    # Check budget gate (40% of total budget)
    if current_monthly_spend > 100.0:  # Assuming $100 monthly budget example
        # Skip non-mandatory Opus invocations
        for category in OPUS_SKIP_CATEGORIES:
            if category in query_lower:
                return False

    # Check mandatory categories
    for category in OPUS_MANDATORY_CATEGORIES:
        if category in query_lower:
            return True

    # Tier 3 queries get Opus by default
    if tier == "tier_3":
        return True

    # Tier 2 and Tier 1 skip Opus by default
    return False


def get_models_for_tier(tier: str) -> list:
    """
    Get the list of models for a given tier.

    Args:
        tier: Tier name ("tier_1", "tier_2", "tier_3", "tier_3_lite")

    Returns:
        List of model names for this tier
    """
    if tier not in TIER_CONFIG:
        raise ValueError(f"Unknown tier: {tier}")
    return TIER_CONFIG[tier]["models"]


def estimate_tier_cost(tier: str) -> tuple[float, float]:
    """
    Get the estimated cost range for a tier.

    Args:
        tier: Tier name

    Returns:
        Tuple of (min_cost, max_cost) in USD
    """
    if tier not in TIER_CONFIG:
        raise ValueError(f"Unknown tier: {tier}")
    return TIER_CONFIG[tier]["estimated_cost"]
