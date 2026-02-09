#!/usr/bin/env python3
"""
schemas.py - Output schemas and validation for Council system

Addresses Council Blocker: Unstructured output risk
- Defines structured output formats
- Validates outputs before passing between modes
- Quality gate validation
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


# ============================================================================
# OUTPUT SCHEMAS
# ============================================================================

class IdeaSchema:
    """Schema for brainstorming ideas."""

    REQUIRED_FIELDS = ["title", "description", "source_model"]
    OPTIONAL_FIELDS = ["tags", "confidence", "category"]

    @staticmethod
    def validate(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate an idea object.

        Returns:
            (is_valid, error_message)
        """
        for field in IdeaSchema.REQUIRED_FIELDS:
            if field not in data:
                return False, f"Missing required field: {field}"

        if not isinstance(data.get("title"), str) or len(data["title"]) == 0:
            return False, "Title must be a non-empty string"

        if not isinstance(data.get("description"), str) or len(data["description"]) == 0:
            return False, "Description must be a non-empty string"

        return True, None

    @staticmethod
    def from_text(text: str, source_model: str) -> Dict[str, Any]:
        """
        Parse idea from text output.

        Args:
            text: Raw model output
            source_model: Which model generated this

        Returns:
            Parsed idea dictionary
        """
        # Try to parse as JSON first
        try:
            data = json.loads(text)
            if IdeaSchema.validate(data)[0]:
                return data
        except json.JSONDecodeError:
            pass

        # Parse as structured text
        # Look for patterns like "Title: ..." or "- **Title** ..."
        title = "Untitled Idea"
        description = text.strip()

        # Try to extract title
        title_patterns = [
            r"^#+\s+(.+?)$",  # Markdown heading
            r"^(.+?)$",  # First line if it looks like a title
        ]

        lines = text.split("\n")
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if re.match(r"^#+\s+", line):
                title = re.sub(r"^#+\s+", "", line).strip()
                break
            if len(line) < 100 and line:  # Short line might be title
                title = line
                break

        return {
            "title": title,
            "description": description,
            "source_model": source_model,
            "tags": [],
            "confidence": 0.5,
        }


class RefinementSchema:
    """Schema for refinement outputs."""

    REQUIRED_FIELDS = ["content", "round", "critique_found", "approved"]
    OPTIONAL_FIELDS = ["issues", "improvements", "next_step"]

    @staticmethod
    def validate(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate refinement output."""
        for field in RefinementSchema.REQUIRED_FIELDS:
            if field not in data:
                return False, f"Missing required field: {field}"

        if not isinstance(data.get("content"), str) or len(data["content"]) == 0:
            return False, "Content must be a non-empty string"

        return True, None


class BuildPlanSchema:
    """Schema for build plan outputs."""

    REQUIRED_FIELDS = ["status", "specification", "implementation_plan"]
    OPTIONAL_FIELDS = ["risks", "success_criteria", "dependencies", "council_decisions"]

    STATUSES = ["APPROVED", "CONDITIONAL", "REJECTED"]

    @staticmethod
    def validate(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate build plan output."""
        if "status" not in data:
            return False, "Missing status field"

        if data["status"] not in BuildPlanSchema.STATUSES:
            return False, f"Invalid status: {data['status']}"

        if not isinstance(data.get("specification"), dict):
            return False, "Specification must be a dictionary"

        if not isinstance(data.get("implementation_plan"), list):
            return False, "Implementation plan must be a list"

        return True, None


# ============================================================================
# QUALITY GATES
# ============================================================================

class QualityGate:
    """Quality gate validation for Council outputs."""

    @staticmethod
    def validate_idea(idea: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate an idea before passing to synthesizer.

        Returns:
            (passes, reason)
        """
        # Check required fields
        valid, error = IdeaSchema.validate(idea)
        if not valid:
            return False, f"Invalid idea structure: {error}"

        # Check minimum quality
        if len(idea.get("description", "")) < 20:
            return False, "Description too short (min 20 chars)"

        # Check for PII/sensitive content
        sensitive_patterns = [
            r'(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+',
            r'(?i)sk-[a-zA-Z0-9]{20,}',
            r'(?i)ghp_[a-zA-Z0-9]{36,}',
        ]

        desc = idea.get("description", "")
        for pattern in sensitive_patterns:
            if re.search(pattern, desc):
                return False, "Contains potentially sensitive information"

        return True, None

    @staticmethod
    def validate_refinement_output(output: str, round_num: int) -> tuple[bool, Optional[str]]:
        """
        Validate refinement output before next round.

        Returns:
            (passes, reason)
        """
        if not output or len(output.strip()) < 50:
            return False, f"Round {round_num} output too short or empty"

        # Check if model actually did refinement (not just "looks good")
        unhelpful_patterns = [
            r"^(looks good|fine|ok|approved|no issues)$",
            r"^(i agree|agree|sounds good)$",
            r"^(no changes|no improvements needed)$",
        ]

        output_lower = output.strip().lower()
        for pattern in unhelpful_patterns:
            if re.match(pattern, output_lower):
                return False, f"Round {round_num} provided no actual refinement"

        # Check for structured critique
        has_critique = (
            "concern" in output_lower
            or "issue" in output_lower
            or "problem" in output_lower
            or "improve" in output_lower
            or "recommend" in output_lower
            or "however" in output_lower
        )

        if round_num > 1 and not has_critique:
            return False, f"Round {round_num} lacks critical review"

        return True, None

    @staticmethod
    def validate_build_plan(plan: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate build plan before saving.

        Returns:
            (passes, reason)
        """
        valid, error = BuildPlanSchema.validate(plan)
        if not valid:
            return False, f"Invalid build plan structure: {error}"

        # Check for required sections
        spec = plan.get("specification", {})
        if not spec.get("components") and not spec.get("architecture"):
            return False, "Specification missing components or architecture"

        impl = plan.get("implementation_plan", [])
        if not impl or len(impl) == 0:
            return False, "Implementation plan is empty"

        # Check for risks section
        if not plan.get("risks"):
            return False, "Build plan must include risk assessment"

        # Check for success criteria
        if not plan.get("success_criteria"):
            return False, "Build plan must include success criteria"

        return True, None


# ============================================================================
# ROLLBACK MECHANISM
# ============================================================================

class RollbackStore:
    """
    Store original states for rollback capability.

    Addresses Council Blocker: No rollback mechanism in refinement
    """

    def __init__(self):
        self.states = {}  # session_id -> list of states

    def save_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save a state for potential rollback."""
        if session_id not in self.states:
            self.states[session_id] = []
        self.states[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "state": state,
        })

    def get_original(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the original state (first saved)."""
        if session_id not in self.states or not self.states[session_id]:
            return None
        return self.states[session_id][0]["state"]

    def get_previous(self, session_id: str, steps_back: int = 1) -> Optional[Dict[str, Any]]:
        """Get a previous state."""
        if session_id not in self.states or not self.states[session_id]:
            return None
        idx = len(self.states[session_id]) - 1 - steps_back
        if idx < 0:
            return None
        return self.states[session_id][idx]["state"]

    def get_latest(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest state."""
        if session_id not in self.states or not self.states[session_id]:
            return None
        return self.states[session_id][-1]["state"]

    def list_states(self, session_id: str) -> List[Dict[str, Any]]:
        """List all states for a session."""
        if session_id not in self.states:
            return []
        return self.states[session_id]


# Singleton rollback store
_rollback_store = None


def get_rollback_store() -> RollbackStore:
    """Get the singleton rollback store."""
    global _rollback_store
    if _rollback_store is None:
        _rollback_store = RollbackStore()
    return _rollback_store
