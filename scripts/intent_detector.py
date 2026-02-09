#!/usr/bin/env python3
"""
intent_detector.py - Auto-detect user intent for Council mode routing

Determines which Council mode to use based on user input keywords.
"""

import re
from typing import Optional, Tuple

# Keyword patterns for each mode
BRAINSTORMING_KEYWORDS = [
    "ways to", "ideas for", "brainstorm", "list possible", "generate ideas",
    "what are possible", "suggest", "options for", "alternatives",
    "could we", "what if", "how might we", "multiple approaches",
]

REFINEMENT_KEYWORDS = [
    "review", "improve", "refine", "critique", "analyze this",
    "find flaws", "better approach", "enhance", "polish",
    "fix this", "optimize", "strengthen", "validate",
]

BUILD_PLANNING_KEYWORDS = [
    "build", "implement", "create", "specify", "design system",
    "architecture for", "implementation plan", "how to build",
    "spec for", "technical specification", "generate build plan",
    "I need to build", "want to create", "help me design",
]

# Mode names
MODE_BRAINSTORMING = "brainstorm"
MODE_REFINEMENT = "refine"
MODE_BUILD_PLANNING = "plan"  # Matches team-debate
MODE_AUTO = "auto"


def detect_intent(user_input: str) -> Tuple[str, float]:
    """
    Detect which Council mode to use based on user input.

    Args:
        user_input: User's request

    Returns:
        (mode, confidence) tuple
        - mode: "brainstorm", "refine", "plan", or "auto"
        - confidence: 0.0 to 1.0 (1.0 = certain)
    """
    if not user_input:
        return MODE_AUTO, 0.0

    input_lower = user_input.lower()

    # Check each mode's keywords
    brainstorm_score = sum(1 for kw in BRAINSTORMING_KEYWORDS if kw in input_lower)
    refine_score = sum(1 for kw in REFINEMENT_KEYWORDS if kw in input_lower)
    plan_score = sum(1 for kw in BUILD_PLANNING_KEYWORDS if kw in input_lower)

    scores = {
        MODE_BRAINSTORMING: brainstorm_score,
        MODE_REFINEMENT: refine_score,
        MODE_BUILD_PLANNING: plan_score,
    }

    # Find highest score
    max_score = max(scores.values())

    if max_score == 0:
        return MODE_AUTO, 0.0

    # Get mode with highest score
    detected_mode = max(scores, key=scores.get)
    confidence = min(max_score / 3.0, 1.0)  # Normalize to 0-1

    return detected_mode, confidence


def get_mode_for_command(command: str) -> str:
    """
    Get the mode for an explicit command.

    Args:
        command: Command name (e.g., "brainstorm", "refine", "plan")

    Returns:
        Mode identifier
    """
    command_map = {
        "brainstorm": MODE_BRAINSTORMING,
        "brain": MODE_BRAINSTORMING,
        "ideas": MODE_BRAINSTORMING,
        "refine": MODE_REFINEMENT,
        "refinement": MODE_REFINEMENT,
        "critique": MODE_REFINEMENT,
        "review": MODE_REFINEMENT,
        "plan": MODE_BUILD_PLANNING,
        "spec": MODE_BUILD_PLANNING,
        "specify": MODE_BUILD_PLANNING,
        "build": MODE_BUILD_PLANNING,
    }

    return command_map.get(command.lower(), MODE_AUTO)


def format_mode_description(mode: str) -> str:
    """
    Get a human-readable description of a mode.

    Args:
        mode: Mode identifier

    Returns:
        Description string
    """
    descriptions = {
        MODE_BRAINSTORMING: "Brainstorming - Generate diverse ideas in parallel",
        MODE_REFINEMENT: "Refinement - Critical review and iterative improvement",
        MODE_BUILD_PLANNING: "Build Planning - Detailed technical specifications",
        MODE_AUTO: "Auto-detect based on your request",
    }
    return descriptions.get(mode, "Unknown mode")
