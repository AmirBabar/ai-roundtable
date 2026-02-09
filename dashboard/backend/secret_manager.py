#!/usr/bin/env python3
"""
Secret Management Architecture

Per Council Decree (Diamond Debate 2026-02-07):
NEVER expose raw API key values to the frontend.

This module provides safe handling of sensitive configuration values:
- Parses config values to detect environment variable references
- Returns masked previews (e.g., "sk-...3Fj2") instead of actual values
- Validates that updates use env var format, not direct values
"""

import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum


class SecretResolution(Enum):
    """How a secret value is resolved."""
    DIRECT = "direct"           # Value stored directly (NOT for API keys)
    ENV_VAR = "env_var"         # Reference to environment variable
    KEYCHAIN = "keychain"       # System keychain reference (future)


@dataclass
class SecretReference:
    """
    Represents a secret without exposing its value.

    This is the ONLY way secrets should be sent to the frontend.
    """
    resolution_type: SecretResolution
    reference: str              # e.g., "OPENAI_API_KEY" for env vars
    is_set: bool               # Whether the secret has a value
    masked_preview: str        # e.g., "sk-...3Fj2"


class SecretManager:
    """
    Manages secrets without exposing raw values to frontend.

    Enforces LiteLLM's os.environ/VAR_NAME pattern for API keys.
    """

    # Matches LiteLLM's environment variable syntax
    # os.environ/VAR_NAME or os.environ["VAR_NAME"] or os.environ['VAR_NAME']
    ENV_VAR_PATTERN = re.compile(r'^os\.environ(?:/|\[)["\']?(\w+)["\']?\]?$')

    def __init__(self):
        """Initialize secret manager."""
        self._warnings = []

    def parse_secret_field(self, value: str, field_name: str = "") -> SecretReference:
        """
        Parse a config value and return a safe reference.

        Args:
            value: The config value (may be env var reference or direct)
            field_name: Name of the field for error messages

        Returns:
            SecretReference with masked preview, never actual value
        """
        if not value:
            return SecretReference(
                resolution_type=SecretResolution.ENV_VAR,
                reference="",
                is_set=False,
                masked_preview=""
            )

        # Check if it's an environment variable reference
        match = self.ENV_VAR_PATTERN.match(value)
        if match:
            env_name = match.group(1)
            actual_value = os.environ.get(env_name, "")
            is_set = bool(actual_value)

            if not is_set:
                self._warnings.append(f"Environment variable not set: {env_name}")

            return SecretReference(
                resolution_type=SecretResolution.ENV_VAR,
                reference=env_name,
                is_set=is_set,
                masked_preview=self._mask_value(actual_value) if actual_value else ""
            )

        # Direct value (legacy support, but flag it)
        # Check if it looks like an actual API key
        if self._looks_like_api_key(value):
            self._warnings.append(
                f"{field_name}: Direct API key detected. "
                f"Use os.environ/{self._guess_env_var_name(field_name)} format instead."
            )

        return SecretReference(
            resolution_type=SecretResolution.DIRECT,
            reference="[DIRECT_VALUE]",  # Never expose to frontend
            is_set=True,
            masked_preview=self._mask_value(value)
        )

    def _mask_value(self, value: str) -> str:
        """
        Create a safe preview of a secret value.

        Shows first 3 and last 3 characters for verification.
        """
        if len(value) <= 6:
            return "•" * len(value)
        return f"{value[:3]}...{value[-3:]}"

    def _looks_like_api_key(self, value: str) -> bool:
        """Check if value looks like an actual API key (not env var reference)."""
        if not value:
            return False

        # Common API key prefixes
        api_prefixes = [
            'sk-', 'sk_',
            'key-', 'key_',
            'api_', 'apikey',
            'Bearer ',
            'ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_',  # GitHub
            'AKIA',  # AWS
            'ya29',  # Google
        ]

        value_lower = value.lower()
        return any(value.startswith(prefix.lower()) for prefix in api_prefixes)

    def _guess_env_var_name(self, field_name: str) -> str:
        """Guess appropriate env var name from field name."""
        # Common mappings
        mappings = {
            'api_key': 'API_KEY',
            'apikey': 'API_KEY',
            'anthropic_key': 'ANTHROPIC_API_KEY',
            'openai_key': 'OPENAI_API_KEY',
            'google_key': 'GOOGLE_API_KEY',
            'deepseek_key': 'DEEPSEEK_API_KEY',
        }

        field_lower = field_name.lower().replace('_', '')

        for pattern, env_var in mappings.items():
            if pattern in field_lower:
                return env_var

        # Default: uppercase field name
        return field_name.upper()

    def serialize_for_frontend(self, secret_ref: SecretReference) -> dict:
        """
        Return frontend-safe representation.

        NEVER includes actual value - only masked preview.
        """
        return {
            'type': secret_ref.resolution_type.value,
            'reference': secret_ref.reference if secret_ref.resolution_type == SecretResolution.ENV_VAR else None,
            'is_set': secret_ref.is_set,
            'preview': secret_ref.masked_preview
        }

    def validate_secret_update(self, field_name: str, new_value: str) -> Tuple[bool, str]:
        """
        Validate a secret update request.

        Enforces environment variable format for API keys.
        Only allows direct values for non-sensitive fields.

        Args:
            field_name: Name of the field being updated
            new_value: New value from request

        Returns:
            (is_valid, error_message)
        """
        if not new_value:
            return True, ""

        # Check if it's an env var reference (always allowed)
        if self.ENV_VAR_PATTERN.match(new_value):
            return True, ""

        # Check if it looks like an API key being stored directly
        if self._looks_like_api_key(new_value):
            return False, (
                f"Direct API keys not allowed for '{field_name}'. "
                f"Use os.environ/{self._guess_env_var_name(field_name)} format."
            )

        # Direct value allowed for non-sensitive fields
        return True, ""

    def get_warnings(self) -> list:
        """Get accumulated warnings and clear them."""
        warnings = self._warnings.copy()
        self._warnings.clear()
        return warnings


# Singleton instance
secret_manager = SecretManager()


if __name__ == "__main__":
    # Test the secret manager
    print("Testing SecretManager...")

    # Test env var reference
    test_ref = secret_manager.parse_secret_field("os.environ/OPENAI_API_KEY", "api_key")
    print(f"Env var ref: {secret_manager.serialize_for_frontend(test_ref)}")

    # Test direct value
    test_direct = secret_manager.parse_secret_field("sk-abc123def456", "api_key")
    print(f"Direct value: {secret_manager.serialize_for_frontend(test_direct)}")

    # Test validation
    valid, msg = secret_manager.validate_secret_update("api_key", "sk-bad123")
    print(f"Validation (direct): {valid}, {msg}")

    valid, msg = secret_manager.validate_secret_update("api_key", "os.environ/OPENAI_API_KEY")
    print(f"Validation (env var): {valid}, {msg}")
