#!/usr/bin/env python3
"""
Authentication Layer for Configuration Endpoints

Per Council Decree (Diamond Debate 2026-02-07):
All configuration endpoints MUST be protected by authentication.

Uses simple token-based authentication compatible with existing dashboard.
Reuses dashboard's existing auth token from .auth-token file for consistency.
"""

import secrets
import os
from functools import wraps
from typing import Callable
from pathlib import Path

# Import existing dashboard token system
TOKEN_PATH = Path(__file__).parent.parent / "data" / ".auth-token"


class ConfigAuth:
    """
    Token-based authentication for config endpoints.

    Reuses existing dashboard auth token for consistency.
    Config endpoints require the same token as other dashboard APIs.
    """

    def __init__(self):
        """Initialize auth with existing dashboard token."""
        self._load_token()

    def _load_token(self):
        """Load existing dashboard token or generate new one."""
        if TOKEN_PATH.exists():
            self.valid_token = TOKEN_PATH.read_text().strip()
        else:
            # Create token if it doesn't exist (same as server.py does)
            self.valid_token = secrets.token_urlsafe(32)
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(self.valid_token)
            print(f"[CONFIG AUTH] Created new token: {self.valid_token}")

    def require_auth(self, f: Callable) -> Callable:
        """
        Decorator for protected endpoints.

        Requires X-Config-Token header to match valid_token.
        Also accepts existing dashboard token via query param for consistency.
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get request object (first arg is typically self/handler)
            # For SimpleHTTPRequestHandler, we need to access via args[0]
            if hasattr(args[0], 'headers'):
                headers = args[0].headers
                # Check X-Config-Token header
                token = headers.get('X-Config-Token', '')
                if token and secrets.compare_digest(token, self.valid_token):
                    return f(*args, **kwargs)

                # Check existing dashboard token query param (for consistency)
                # Parse query string from path
                if hasattr(args[0], 'path'):
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(args[0].path)
                    query = parse_qs(parsed.query)
                    if 'token' in query and query['token'][0] == self.valid_token:
                        return f(*args, **kwargs)

            # Unauthorized - return 401
            return self._unauthorized(args[0])

        return decorated

    def _unauthorized(self, handler):
        """Send 401 Unauthorized response."""
        handler.send_response(401)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()

        import json
        response = {
            "error": "Unauthorized",
            "message": "Valid X-Config-Token header or ?token= parameter required"
        }
        handler.wfile.write(json.dumps(response).encode())
        return None


# Singleton instance for import
config_auth = ConfigAuth()


def require_config_auth(f):
    """
    Convenience decorator that can be used without instantiating ConfigAuth.

    Usage:
        @require_config_auth
        def my_endpoint(self):
            ...
    """
    return config_auth.require_auth(f)


if __name__ == "__main__":
    # Test the auth module
    print("Config Auth Token:", config_auth.valid_token)
    print(f"Token Path: {TOKEN_PATH}")
