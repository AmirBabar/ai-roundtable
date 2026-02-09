#!/usr/bin/env python3
"""
paths.py - Cross-platform path handling for AI Roundtable

Provides path resolution utilities that work with the ai-roundtable
distribution, whether installed as a skill or run standalone.
"""

import re
import os
from pathlib import Path
from typing import Optional


def get_repo_root() -> Path:
    """
    Get the AI Roundtable repository root directory.

    This detects the repo root by looking for key files/directories.
    Works whether run as a skill or standalone.

    Returns:
        Path: The repository root directory
    """
    # Start from this file's location
    current = Path(__file__).resolve().parent

    # Look for repo markers
    markers = ['SKILL.md', 'scripts', 'config', 'README.md']

    while current != current.parent:
        if all((current / m).exists() for m in markers[:2]):  # Check minimum markers
            return current
        current = current.parent

    # Fallback: assume we're in lib/ and parent is root
    return Path(__file__).resolve().parent.parent


def get_build_plans_dir() -> Path:
    """Get the build plans directory."""
    return get_repo_root() / "build-plans"


def get_config_dir() -> Path:
    """Get the configuration directory."""
    return get_repo_root() / "config"


def get_litellm_config_path() -> Optional[Path]:
    """
    Get the LiteLLM configuration file path.

    Returns config.yaml if it exists, otherwise config.yaml.example
    """
    config_dir = get_repo_root() / "litellm"
    config_path = config_dir / "config.yaml"

    if config_path.exists():
        return config_path

    # Return example path for reference
    example_path = config_dir / "config.yaml.example"
    return example_path if example_path.exists() else None


def convert_posix_to_windows(path: str) -> str:
    """
    Convert POSIX-style paths to Windows format.

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


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    root = get_repo_root()
    dirs = [
        root / "build-plans",
        root / "config",
        root / "memory" / "data",
        root / "dashboard" / "data",
        root / "litellm" / "logs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


__all__ = [
    "get_repo_root",
    "get_build_plans_dir",
    "get_config_dir",
    "get_litellm_config_path",
    "convert_posix_to_windows",
    "sanitize_filename",
    "sanitize_path_for_display",
    "safe_path_join",
    "ensure_directories",
]
