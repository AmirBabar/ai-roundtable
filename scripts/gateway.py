#!/usr/bin/env python3
"""
gateway.py - Unified model gateway for Council system

Addresses Council Blocker: Unicode/encoding issues on Windows
- UTF-8 throughout
- Proper error handling
- Model fallbacks
- Timeout management
"""

import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Bootstrap: Add scripts directory to path for direct script execution
# Per Council: lib/__init__.py bootstrap_module_context pattern
current_path = Path(__file__).resolve()
scripts_dir = current_path.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# Use absolute imports (relative imports don't work when script run directly)
from models import GATEWAY_URL, MODEL_FALLBACKS


class CouncilGateway:
    """Unified gateway for all Council model calls."""

    def __init__(self):
        """Initialize the gateway."""
        self.gateway_url = GATEWAY_URL
        self.default_timeout = 120
        self.max_retries = 2

    def call_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Call a model via the LiteLLM gateway.

        Args:
            model: Model identifier
            system_prompt: System message
            user_prompt: User message
            timeout: Request timeout in seconds
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            Dictionary with:
                - success (bool)
                - content (str): Model response
                - model (str): Model that responded
                - tokens (int): Tokens used (if available)
                - error (str): Error message if failed
        """
        timeout = timeout or self.default_timeout

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.gateway_url,
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()

                data = response.json()

                # Extract content safely
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as e:
                    return {
                        "success": False,
                        "content": None,
                        "model": model,
                        "tokens": 0,
                        "error": f"Invalid response format: {e}",
                    }

                return {
                    "success": True,
                    "content": content,
                    "model": model,
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "error": None,
                }

            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    continue
                return {
                    "success": False,
                    "content": None,
                    "model": model,
                    "tokens": 0,
                    "error": f"Request timeout after {timeout}s",
                }

            except requests.exceptions.RequestException as e:
                # Try fallback model
                fallback = MODEL_FALLBACKS.get(model)
                if fallback and attempt == 0:
                    return self.call_model(
                        fallback,
                        system_prompt,
                        user_prompt,
                        timeout,
                        temperature,
                        max_tokens,
                    )
                return {
                    "success": False,
                    "content": None,
                    "model": model,
                    "tokens": 0,
                    "error": f"Request failed: {str(e)[:100]}",
                }

            except Exception as e:
                return {
                    "success": False,
                    "content": None,
                    "model": model,
                    "tokens": 0,
                    "error": f"Unexpected error: {str(e)[:100]}",
                }

        return {
            "success": False,
            "content": None,
            "model": model,
            "tokens": 0,
            "error": "Max retries exceeded",
        }


def sanitize_output(text: str) -> str:
    """
    Sanitize model output to prevent encoding issues.

    Addresses Council Blocker: Unicode/encoding on Windows
    - Replace problematic characters
    - Ensure ASCII-safe output

    Args:
        text: Raw model output

    Returns:
        Sanitized text safe for Windows console
    """
    if not text:
        return text

    # Replace common problematic Unicode with ASCII alternatives
    replacements = {
        '\u2018': "'",  # Left single quotation mark
        '\u2019': "'",  # Right single quotation mark
        '\u201c': '"',  # Left double quotation mark
        '\u201d': '"',  # Right double quotation mark
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2022': '*',  # Bullet
        '\u2192': '->', # Right arrow
        '\u2190': '<-', # Left arrow
        '\u2191': '^',  # Up arrow
        '\u2193': 'v',  # Down arrow
        '\u2713': '[OK]', # Check mark
        '\u2717': '[X]',  # Ballot X
        '\u26a0': '[!]', # Warning sign
        '\u27a2': '[INFO]', # Information
    }

    for unicode_char, ascii_replacement in replacements.items():
        text = text.replace(unicode_char, ascii_replacement)

    # Remove any remaining non-ASCII characters (except newlines and tabs)
    # This is a fallback - should rarely be needed with proper replacements above
    try:
        text.encode('ascii')
    except UnicodeEncodeError:
        # Encode with ascii error handling
        text = text.encode('ascii', errors='replace').decode('ascii')

    return text


def print_safe(text: str, file=None):
    """
    Print text safely to avoid Unicode encoding errors.

    Addresses Council Blocker: Console output corruption on Windows

    Args:
        text: Text to print
        file: File object (defaults to sys.stdout)
    """
    if file is None:
        file = sys.stdout

    try:
        print(text, file=file)
    except UnicodeEncodeError:
        # Fallback to sanitized output
        print(sanitize_output(text), file=file)


# Singleton gateway instance
_gateway = None


def get_gateway() -> CouncilGateway:
    """Get the singleton gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = CouncilGateway()
    return _gateway


# CLI for testing
if __name__ == "__main__":
    import io

    # Fix stdout encoding for Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    gateway = get_gateway()

    print("=== Council Gateway Test ===")

    # Test with a simple call
    result = gateway.call_model(
        model="gemini-flash",
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello in one sentence.",
        timeout=30,
    )

    if result["success"]:
        print(f"Model: {result['model']}")
        print(f"Tokens: {result['tokens']}")
        print(f"Response: {result['content'][:200]}")
    else:
        print(f"Error: {result['error']}")
