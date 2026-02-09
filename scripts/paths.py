#!/usr/bin/env python3
"""
paths.py - Cross-platform path handling for Council system

Addresses Council Blocker: Path handling issues on Windows
- Convert POSIX paths to Windows
- Sanitize filenames for Windows compatibility
- Handle MINGW paths
"""

import re
import os
from pathlib import Path
from typing import Optional


def convert_posix_to_windows(path: str) -> str:
    """
    Convert POSIX-style paths to Windows format.

    Addresses Council Blocker: Agents generate POSIX paths that fail on Windows

    Args:
        path: POSIX path (e.g., "/home/user/.claude/file.txt")

    Returns:
        Windows-compatible path (e.g., "C:\\Users\\user\\.claude\\file.txt")
    """
    if not path:
        return path

    # If it looks like a Windows path already, return as-is
    if re.match(r'^[A-Za-z]:\\', path):
        return path

    # Replace forward slashes with backslashes
    path = path.replace('/', '\\')

    # Handle ~ expansion
    if path.startswith('~\\'):
        home = str(Path.home())
        path = home + path[1:]

    return path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for Windows compatibility.

    Addresses Council Blocker: Filenames with illegal characters

    Args:
        filename: Proposed filename

    Returns:
        Sanitized filename safe for Windows
    """
    if not filename:
        return filename

    # Windows illegal characters: < > : " / \ | ? *
    illegal_chars = r'[<>:"/\\|?*]'
    filename = re.sub(illegal_chars, '_', filename)

    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')

    # Limit length (Windows max is 255, but let's be safe)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext

    return filename


def sanitize_path_for_display(path: str) -> str:
    """
    Sanitize path for display (hide user-specific info).

    Args:
        path: Original path

    Returns:
        Sanitized path for display
    """
    if not path:
        return path

    # Convert to Path object for manipulation
    p = Path(path)

    # Try to make relative to home directory
    try:
        home = Path.home()
        if p.is_absolute():
            try:
                rel = p.relative_to(home)
                return f"~/{rel}"
            except ValueError:
                # Not under home, return just filename
                return p.name
    except Exception:
        pass

    # Fallback: return just filename
    return p.name


def safe_path_join(*parts: str) -> str:
    """
    Join path parts safely for current platform.

    Args:
        *parts: Path components

    Returns:
        Platform-appropriate joined path
    """
    return str(Path(*parts).as_posix())


def get_council_dir() -> Path:
    """Get the council skill directory."""
    return Path.home() / ".claude" / "skills" / "council"


def get_build_plans_dir() -> Path:
    """Get the build plans directory."""
    return get_council_dir() / "build-plans"


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    dirs = [
        get_council_dir(),
        get_build_plans_dir(),
        get_council_dir() / "scripts",
        get_council_dir() / "references",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
