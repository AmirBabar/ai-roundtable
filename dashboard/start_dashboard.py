#!/usr/bin/env python3
"""
Council Skill - Dashboard Launcher (Cross-Platform)

Launches the Council dashboard web interface.
Works on Windows, macOS, and Linux.

Usage:
    python start_dashboard.py
    python start_dashboard.py --port 8080
    python start_dashboard.py --debug
"""

import sys
import subprocess
import argparse
import shutil
import time
import webbrowser
from pathlib import Path

# Import path resolver for skill-root awareness
try:
    from lib.path_resolver import SKILL_ROOT, DASHBOARD_BACKEND_DIR
except ImportError:
    # Fallback if running directly
    SKILL_ROOT = Path(__file__).parent.parent
    DASHBOARD_BACKEND_DIR = SKILL_ROOT / "dashboard" / "backend"


def find_python_executable():
    """
    Get the current Python executable.

    Returns:
        Path: The path to the current Python interpreter
    """
    return Path(sys.executable)


def check_dashboard_files():
    """
    Check if dashboard files exist.

    Returns:
        bool: True if dashboard files are present
    """
    server_file = DASHBOARD_BACKEND_DIR / "server.py"
    if not server_file.exists():
        print(f"ERROR: Dashboard server not found: {server_file}", file=sys.stderr)
        return False
    return True


def launch_dashboard(
    port: int = 8080,
    host: str = "127.0.0.1",
    debug: bool = False,
    open_browser: bool = True
):
    """
    Launch the Council dashboard.

    Args:
        port: Port for the dashboard (default: 8080)
        host: Host to bind to (default: 127.0.0.1)
        debug: Enable debug mode (default: False)
        open_browser: Open web browser automatically (default: True)
    """
    # Check dashboard files
    if not check_dashboard_files():
        sys.exit(1)

    # Get Python executable
    python_exe = find_python_executable()

    # Build command
    server_file = DASHBOARD_BACKEND_DIR / "server.py"
    cmd = [
        str(python_exe),
        str(server_file),
        "--port", str(port),
        "--host", host,
    ]

    if debug:
        cmd.append("--debug")

    # Print launch info
    print("=" * 60)
    print("Council Dashboard Launcher")
    print("=" * 60)
    print(f"Python: {python_exe}")
    print(f"Server: {server_file}")
    print(f"URL: http://{host}:{port}")
    print("=" * 60)
    print("Starting dashboard...")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # Open browser after a short delay
    if open_browser:
        def open_browser_delayed():
            time.sleep(2)  # Wait for server to start
            try:
                webbrowser.open(f"http://{host}:{port}")
                print(f"Opened browser at http://{host}:{port}")
            except Exception as e:
                print(f"Note: Could not open browser: {e}")

        import threading
        threading.Thread(target=open_browser_delayed, daemon=True).start()

    try:
        # Launch dashboard (blocking)
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Dashboard exited with code {e.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"\nERROR: Cannot execute {python_exe}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Launch Council Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Launch on default port 8080
  %(prog)s --port 9000        # Launch on port 9000
  %(prog)s --debug            # Enable debug mode
  %(prog)s --no-browser       # Don't open browser
        """
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port for the dashboard (default: 8080)"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open web browser"
    )

    args = parser.parse_args()

    launch_dashboard(
        port=args.port,
        host=args.host,
        debug=args.debug,
        open_browser=not args.no_browser
    )


if __name__ == "__main__":
    main()
