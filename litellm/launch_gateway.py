#!/usr/bin/env python3
"""
Council Skill - LiteLLM Gateway Launcher (Cross-Platform)

Launches the LiteLLM gateway with the Council configuration.
Works on Windows, macOS, and Linux.

Usage:
    python launch_gateway.py
    python launch_gateway.py --port 4001
    python launch_gateway.py --help
"""

import sys
import subprocess
import argparse
import shutil
from pathlib import Path

# Import path resolver for skill-root awareness
try:
    from lib.path_resolver import SKILL_ROOT, get_litellm_config_path
except ImportError:
    # Fallback if running directly
    SKILL_ROOT = Path(__file__).parent.parent
    def get_litellm_config_path():
        return SKILL_ROOT / "litellm" / "config.yaml"


def find_litellm_executable():
    """
    Find the litellm executable on the system.

    Searches for litellm in:
    1. Python Scripts directory (Windows)
    2. Python bin directory (Unix)
    3. System PATH via shutil.which()

    Returns:
        Path or str: The path to litellm executable, or None if not found
    """
    # Try shutil.which first (most reliable)
    litellm_path = shutil.which("litellm")
    if litellm_path:
        return Path(litellm_path)

    # Try Python Scripts directory (Windows)
    python_dir = Path(sys.executable).parent
    litellm_exe = python_dir / "Scripts" / "litellm.exe"
    if litellm_exe.exists():
        return litellm_exe

    # Try Python bin directory (Unix)
    litellm_bin = python_dir / "bin" / "litellm"
    if litellm_bin.exists():
        return litellm_bin

    # Try python -m litellm
    return None


def launch_gateway(port: int = 4000, config_path: Path = None, drop_params: bool = True):
    """
    Launch the LiteLLM gateway.

    Args:
        port: Port number for the gateway (default: 4000)
        config_path: Path to litellm config.yaml (default: auto-detected)
        drop_params: Whether to drop unknown parameters (default: True)
    """
    # Auto-detect config path
    if config_path is None:
        config_path = get_litellm_config_path()

    # Verify config exists
    if not config_path.exists():
        print(f"ERROR: LiteLLM config not found: {config_path}", file=sys.stderr)
        print(f"Please create {config_path} or specify --config", file=sys.stderr)
        sys.exit(1)

    # Find litellm executable
    litellm_exe = find_litellm_executable()

    if litellm_exe is None:
        print("ERROR: litellm executable not found", file=sys.stderr)
        print("Install with: pip install litellm", file=sys.stderr)
        sys.exit(1)

    # Build command
    cmd = [
        str(litellm_exe),
        "--config", str(config_path),
        "--port", str(port),
    ]

    if drop_params:
        cmd.append("--drop_params")

    # Disable telemetry (privacy)
    cmd.extend(["--telemetry", "False"])

    # Print launch info
    print("=" * 60)
    print("Council LiteLLM Gateway Launcher")
    print("=" * 60)
    print(f"Executable: {litellm_exe}")
    print(f"Config: {config_path}")
    print(f"Port: {port}")
    print("=" * 60)
    print("Starting gateway...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    flush=True

    try:
        # Launch gateway (blocking)
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nGateway stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Gateway exited with code {e.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"\nERROR: Cannot execute {litellm_exe}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Launch Council LiteLLM Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Launch on default port 4000
  %(prog)s --port 4001        # Launch on port 4001
  %(prog)s --config custom.yaml  # Use custom config
        """
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=4000,
        help="Port for the gateway (default: 4000)"
    )

    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Path to litellm config.yaml (default: auto-detected)"
    )

    parser.add_argument(
        "--no-drop-params",
        action="store_true",
        help="Do not drop unknown parameters"
    )

    args = parser.parse_args()

    launch_gateway(
        port=args.port,
        config_path=args.config,
        drop_params=not args.no_drop_params
    )


if __name__ == "__main__":
    main()
