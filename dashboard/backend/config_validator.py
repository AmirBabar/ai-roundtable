#!/usr/bin/env python3
"""
Server-Side Validation (Zero Trust)

Per Council Decree (Diamond Debate 2026-02-07):
NEVER trust frontend validation. All config data MUST be validated server-side.

This module provides:
- Schema validation using jsonschema
- Path validation (whitelist only, prevents traversal)
- Business logic validation for LiteLLM and Council configs
"""

import jsonschema
import yaml
import os
from pathlib import Path
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings
        }


class ConfigValidator:
    """
    Server-side validation - NEVER trust frontend validation.

    Uses whitelist approach for file paths to prevent traversal.
    Validates both schema structure and business logic rules.
    """

    # Allowed config file paths (whitelist approach)
    # All paths are resolved to absolute paths at initialization
    ALLOWED_PATHS = {}

    def __init__(self, schema_dir: str = None):
        """
        Initialize validator with schema directory.

        Args:
            schema_dir: Path to JSON schema files (default: dashboard/backend/schemas)
        """
        if schema_dir is None:
            schema_dir = Path(__file__).parent / "schemas"
        else:
            schema_dir = Path(schema_dir)

        self.schema_dir = schema_dir
        self._schemas = {}
        self._load_schemas()
        self._init_allowed_paths()

    def _load_schemas(self):
        """Load all JSON schemas on startup."""
        if not self.schema_dir.exists():
            # Schema directory doesn't exist yet, that's ok
            return

        for schema_file in self.schema_dir.glob("*.json"):
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    import json
                    self._schemas[schema_file.stem] = json.load(f)
            except Exception as e:
                print(f"[CONFIG VALIDATOR] Failed to load schema {schema_file}: {e}")

    def _init_allowed_paths(self):
        """Initialize allowed config paths (resolve to absolute)."""
        # Get project root (dashboard/backend -> dashboard -> .claude)
        project_root = Path(__file__).parent.parent.parent

        # Define allowed paths relative to project root
        relative_paths = {
            'litellm': Path('litellm/config.yaml'),
            'council': Path('skills/council/config.yaml'),
        }

        for key, rel_path in relative_paths.items():
            abs_path = (project_root / rel_path).resolve()
            self.ALLOWED_PATHS[key] = abs_path

    def validate_path(self, config_type: str) -> Tuple[bool, Optional[Path]]:
        """
        Validate and resolve config path. Prevents path traversal.

        Args:
            config_type: Type of config ('litellm' or 'council')

        Returns:
            (is_valid, absolute_path) - path is None if invalid
        """
        if config_type not in self.ALLOWED_PATHS:
            return False, None

        # Return the absolute path (already resolved in __init__)
        return True, self.ALLOWED_PATHS[config_type]

    def validate_config(self, config_type: str, data: dict) -> ValidationResult:
        """
        Full server-side validation of configuration data.

        Args:
            config_type: Type of config ('litellm' or 'council')
            data: Configuration data to validate

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # Schema validation
        schema = self._schemas.get(config_type)
        if schema:
            try:
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")
                # Add context to error
                if e.path:
                    errors.append(f"  Location: {' -> '.join(str(p) for p in e.path)}")
                return ValidationResult(False, errors, warnings)
        else:
            # No schema found, skip schema validation
            warnings.append(f"No schema found for config type '{config_type}', skipping schema validation")

        # Business logic validation
        if config_type == 'litellm':
            errors.extend(self._validate_litellm_logic(data))
        elif config_type == 'council':
            errors.extend(self._validate_council_logic(data))

        return ValidationResult(len(errors) == 0, errors, warnings)

    def _validate_litellm_logic(self, data: dict) -> List[str]:
        """
        LiteLLM-specific validation rules.

        Args:
            data: LiteLLM config dict

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate model_list
        model_list = data.get('model_list', [])
        if not model_list:
            errors.append("model_list is required and cannot be empty")
            return errors

        model_names = set()

        for i, model in enumerate(model_list):
            name = model.get('model_name', '')

            # Check for duplicate model names
            if not name:
                errors.append(f"model_list[{i}]: model_name is required")
                continue

            if name in model_names:
                errors.append(f"Duplicate model_name: '{name}'")
            model_names.add(name)

            # Validate litellm_params
            params = model.get('litellm_params', {})
            if not params.get('model'):
                errors.append(f"Model '{name}': litellm_params.model is required")

            # Verify API key format (must be env var reference or empty)
            api_key = params.get('api_key', '')
            if api_key and not api_key.startswith('os.environ'):
                errors.append(
                    f"Model '{name}': API key must use os.environ format, "
                    f"not direct value (found: {api_key[:20]}...)"
                )

            # Validate numeric ranges
            rpm = params.get('rpm')
            if rpm is not None and (not isinstance(rpm, int) or rpm < 1):
                errors.append(f"Model '{name}': rpm must be a positive integer")

            tpm = params.get('tpm')
            if tpm is not None and (not isinstance(tpm, int) or tpm < 1):
                errors.append(f"Model '{name}': tpm must be a positive integer")

            max_tokens = params.get('max_tokens')
            if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens < 1):
                errors.append(f"Model '{name}': max_tokens must be a positive integer")

            timeout = params.get('timeout')
            if timeout is not None and (not isinstance(timeout, int) or not (1 <= timeout <= 600)):
                errors.append(f"Model '{name}': timeout must be between 1 and 600 seconds")

        return errors

    def _validate_council_logic(self, data: dict) -> List[str]:
        """
        Council-specific validation rules.

        Args:
            data: Council config dict

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate defaults section
        defaults = data.get('defaults', {})

        # Validate mode
        valid_modes = {
            'brainstorm', 'refine', 'build-plan', 'build-review',
            'opus-gatekeeper', 'diamond-debate', 'team-debate'
        }
        mode = defaults.get('mode')
        if mode:
            if mode not in valid_modes:
                errors.append(
                    f"Invalid mode: '{mode}'. Must be one of: {', '.join(sorted(valid_modes))}"
                )

        # Validate timeout
        timeout = defaults.get('timeout')
        if timeout is not None:
            if not isinstance(timeout, int) or not (5 <= timeout <= 600):
                errors.append(f"Timeout must be between 5 and 600 seconds, got {timeout}")

        # Validate model assignments exist in LiteLLM config
        # (This is a cross-validation that would require loading LiteLLM config)
        # For now, just check structure
        models = data.get('models', {})

        # Validate build_planning models
        build_planning = models.get('build_planning', {})
        required_roles = ['architect', 'auditor', 'contextualist', 'judge']
        for role in required_roles:
            if not build_planning.get(role):
                errors.append(f"models.build_planning.{role} is required")

        return errors


# Singleton instance
config_validator = ConfigValidator()


if __name__ == "__main__":
    # Test the validator
    print("Testing ConfigValidator...")

    # Test path validation
    valid, path = config_validator.validate_path('litellm')
    print(f"LiteLLM path: {valid} -> {path}")

    valid, path = config_validator.validate_path('council')
    print(f"Council path: {valid} -> {path}")

    valid, path = config_validator.validate_path('malicious')
    print(f"Malicious path: {valid} -> {path}")

    # Test schema validation
    test_config = {
        "model_list": [
            {
                "model_name": "test-model",
                "litellm_params": {
                    "model": "openai/gpt-4o",
                    "api_key": "os.environ/OPENAI_API_KEY"
                }
            }
        ]
    }

    result = config_validator.validate_config('litellm', test_config)
    print(f"Validation result: {result.to_dict()}")
