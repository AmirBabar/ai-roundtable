#!/usr/bin/env python3
"""
Council skill - Multi-tiered AI collaboration system

Four modes for different collaboration needs:
- Mode 1: Brainstorming (parallel light models)
- Mode 2: Refinement (series critical review)
- Mode 3: Build Planning (thorough specifications)
- Mode 4: Build Reviewer (post-build validation)
"""

from .gateway import CouncilGateway, get_gateway, sanitize_output, print_safe
from .models import BRAINSTORMING_MODELS, REFINEMENT_MODELS, BUILD_PLANNING_MODELS
from .schemas import (
    IdeaSchema,
    RefinementSchema,
    BuildPlanSchema,
    QualityGate,
    RollbackStore,
    get_rollback_store,
)
from .paths import (
    convert_posix_to_windows,
    sanitize_filename,
    sanitize_path_for_display,
    safe_path_join,
    get_council_dir,
    get_build_plans_dir,
    ensure_directories,
)
from .brainstorm import brainstorm
from .refine import refine, rollback
from .build_planner import build_planner
from .build_reviewer import review_build, quick_review
from .intent_detector import (
    detect_intent,
    get_mode_for_command,
    format_mode_description,
    MODE_BRAINSTORMING,
    MODE_REFINEMENT,
    MODE_BUILD_PLANNING,
    MODE_AUTO,
)

__all__ = [
    # Gateway
    "CouncilGateway",
    "get_gateway",
    "sanitize_output",
    "print_safe",
    # Models
    "BRAINSTORMING_MODELS",
    "REFINEMENT_MODELS",
    "BUILD_PLANNING_MODELS",
    # Schemas
    "IdeaSchema",
    "RefinementSchema",
    "BuildPlanSchema",
    "QualityGate",
    "RollbackStore",
    "get_rollback_store",
    # Paths
    "convert_posix_to_windows",
    "sanitize_filename",
    "sanitize_path_for_display",
    "safe_path_join",
    "get_council_dir",
    "get_build_plans_dir",
    "ensure_directories",
    # Mode functions
    "brainstorm",
    "refine",
    "rollback",
    "build_planner",
    "review_build",
    "quick_review",
    # Intent detection
    "detect_intent",
    "get_mode_for_command",
    "format_mode_description",
    "MODE_BRAINSTORMING",
    "MODE_REFINEMENT",
    "MODE_BUILD_PLANNING",
    "MODE_AUTO",
]
