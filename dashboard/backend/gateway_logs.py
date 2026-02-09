#!/usr/bin/env python3
"""
Gateway Logs Viewer Backend

Per Council Security Review (2026-02-01):
- MANDATORY: API key scrubbing before streaming
- JSON-based parsing (not ANSI text)
- Windows file locking compatibility
- Path traversal protection
"""

import os
import re
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime

# ============================================================================
# SECURITY SCRUBBER (MANDATORY per Council)
# ============================================================================
# Pre-compiled regex patterns for API key redaction
# API keys WILL leak in logs - must scrub before streaming
API_KEY_PATTERNS = [
    # OpenAI/Anthropic format: sk-...
    re.compile(r'(sk-[a-zA-Z0-9]{20,})'),
    # Bearer tokens
    re.compile(r'(Bearer [a-zA-Z0-9\-._~+/]{20,})'),
    # DeepSeek keys
    re.compile(r'(sk-[a-f0-9]{48})'),
    # Moonshot/Kimi keys
    re.compile(r'(sk-[a-zA-Z0-9]{32,})'),
    # Generic API key pattern (catch-all)
    re.compile(r'("api_key":\s*")[^"]+(")'),
]

SCRUB_REPLACEMENT = r'\1****(redacted)\2' if r'\2' in 'Bearer ' else r'\1****(redacted)'

def scrub_log_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrub sensitive information from log entry.

    Per Council Security Review: API keys WILL appear in logs.
    This function redacts them before streaming to frontend.

    Args:
        entry: Log entry dictionary

    Returns:
        Scrubbed log entry
    """
    # Convert to string for scrubbing (handles nested dict/list)
    entry_str = json.dumps(entry)

    # Apply all scrubbing patterns
    for pattern in API_KEY_PATTERNS:
        entry_str = pattern.sub(lambda m: f"{m.group(1)[:15]}...****(redacted)", entry_str)

    # Parse back to dict
    try:
        return json.loads(entry_str)
    except json.JSONDecodeError:
        # Fallback: return original with sensitive fields removed
        return {
            k: v for k, v in entry.items()
            if k not in ['api_key', 'authorization', 'token']
        }


def get_log_level(entry: Dict[str, Any]) -> str:
    """
    Extract log level from entry.

    Maps various field names to standard levels.
    """
    # Check common level fields
    for field in ['level', 'log_level', 'severity', 'type']:
        if field in entry:
            level = str(entry[field]).upper()
            if level in ['ERROR', 'WARNING', 'INFO', 'DEBUG']:
                return level

    # Infer from status code
    if 'status_code' in entry:
        status = entry['status_code']
        if status >= 500:
            return 'ERROR'
        elif status >= 400:
            return 'WARNING'
        elif status >= 200:
            return 'INFO'

    # Check for error indicators
    entry_str = json.dumps(entry, default=str).lower()
    if any(x in entry_str for x in ['error', 'exception', 'failed', 'invalid']):
        return 'ERROR'

    return 'INFO'


# ============================================================================
# LOG FILE TAILING (Windows-compatible)
# ============================================================================
LOG_DIR = Path(__file__).parent.parent.parent / "litellm" / "logs"
LOG_FILE = LOG_DIR / "proxy.jsonl"

# Path traversal protection (per Council)
# Only allow reading from litellm/logs/ directory
def validate_log_path(path: str) -> bool:
    """
    Validate log path is within allowed directory.

    Per Council Security Review: Prevent path traversal attacks.
    """
    try:
        resolved = Path(path).resolve()
        allowed = LOG_DIR.resolve()
        # Check if resolved path starts with allowed directory
        return str(resolved).startswith(str(allowed))
    except (OSError, ValueError):
        return False


def get_recent_logs(lines: int = 100, level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get recent log lines from file.

    Args:
        lines: Maximum number of lines to return
        level_filter: Optional filter by log level (ERROR, WARNING, INFO)

    Returns:
        List of scrubbed log entries
    """
    if not LOG_FILE.exists():
        return []

    # Path traversal check
    if not validate_log_path(str(LOG_FILE)):
        print(f"[SECURITY] Invalid log path: {LOG_FILE}")
        return []

    try:
        # Windows compatibility: explicit encoding, errors='replace'
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            # Read all lines (for small files) or tail for large ones
            all_lines = f.readlines()

        # Get last N lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # Parse and filter
        entries = []
        for line in reversed(recent_lines):  # Most recent first
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                level = get_log_level(entry)

                # Filter by level if specified
                if level_filter and level != level_filter:
                    continue

                # Scrub sensitive data (MANDATORY)
                entry = scrub_log_entry(entry)
                entry['_level'] = level  # Add computed level
                entries.append(entry)

            except json.JSONDecodeError:
                # Skip invalid JSON lines
                continue

        return entries

    except (OSError, IOError) as e:
        print(f"[ERROR] Failed to read log file: {e}")
        return []


def tail_logs_stream(level_filter: Optional[str] = None) -> Generator[str, None, None]:
    """
    Stream new log lines as they're written (generator).

    Args:
        level_filter: Optional filter by log level

    Yields:
        JSON strings of log entries
    """
    # Wait for log file to be created
    while not LOG_FILE.exists():
        time.sleep(1)

    # Path traversal check
    if not validate_log_path(str(LOG_FILE)):
        yield json.dumps({"error": "Invalid log path"})
        return

    # Track file position for rotation handling - use a set to track seen log signatures
    last_inode = None
    seen_entries = set()  # Track unique entries to avoid duplicates
    last_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0

    while True:
        try:
            # Check for rotation (inode change or size decrease)
            stat = LOG_FILE.stat()
            current_inode = stat.st_ino
            current_size = stat.st_size

            if last_inode and (current_inode != last_inode or current_size < last_size):
                # File was rotated or truncated
                last_size = 0
                seen_entries.clear()  # Reset seen entries on rotation
            last_inode = current_inode

            # Windows compatibility: shared read access
            with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                # Seek to last known position
                if last_size < current_size:
                    f.seek(last_size)

                # Read new lines
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)

                        # Create unique signature to detect duplicates
                        entry_signature = f"{entry.get('timestamp', '')}_{entry.get('message', '')}"

                        # Skip if we've already sent this entry
                        if entry_signature in seen_entries:
                            continue

                        level = get_log_level(entry)

                        # Filter by level if specified
                        if level_filter and level != level_filter:
                            continue

                        # Scrub sensitive data (MANDATORY)
                        entry = scrub_log_entry(entry)
                        entry['_level'] = level

                        yield json.dumps(entry)
                        seen_entries.add(entry_signature)  # Mark as seen
                        last_size = f.tell()

                    except json.JSONDecodeError:
                        continue

                # Update last position
                last_size = f.tell()

        except (OSError, IOError) as e:
            # File may be temporarily locked (Windows) or rotated
            print(f"[WARN] Log read error: {e}")

        # Small delay before checking again
        time.sleep(0.5)


# ============================================================================
# LOG STATISTICS
# ============================================================================
def get_log_stats() -> Dict[str, Any]:
    """
    Get statistics about recent logs.
    """
    recent = get_recent_logs(lines=1000)

    # Count by level
    level_counts = {'ERROR': 0, 'WARNING': 0, 'INFO': 0, 'DEBUG': 0}
    for entry in recent:
        level = entry.get('_level', 'INFO')
        level_counts[level] = level_counts.get(level, 0) + 1

    # Get last error
    last_error = None
    for entry in recent:
        if entry.get('_level') == 'ERROR':
            last_error = entry.get('message', entry.get('error', 'Unknown error'))
            break

    return {
        'total_recent': len(recent),
        'level_counts': level_counts,
        'last_error': last_error,
        'log_file': str(LOG_FILE),
        'log_exists': LOG_FILE.exists()
    }


# ============================================================================
# LOG ROTATION HELPER
# ============================================================================
def ensure_log_directory():
    """
    Ensure log directory exists.
    Called during server startup.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[LOGS] Log directory: {LOG_DIR}")
    print(f"[LOGS] Log file: {LOG_FILE}")
