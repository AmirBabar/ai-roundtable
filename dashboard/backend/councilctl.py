#!/usr/bin/env python3
"""
Council Dashboard Control CLI
Usage:
    councilctl start    - Start dashboard server
    councilctl stop     - Graceful shutdown
    councilctl restart  - Stop then start
    councilctl status   - Check if running and healthy
    councilctl cleanup  - Kill orphaned council processes
    councilctl debug    - Launch browser diagnostics (Condition 3)

Per Council Decree: Resource Awareness Implementation
- Secure PID file management with atomic writes
- Cross-platform process spawning (Windows POSIX)
- Health check verification before declaring "running"
- Graceful shutdown with WAL checkpoint support
"""

from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
import platform
import urllib.request
import urllib.error
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional

# =============================================================================
# CONFIGURATION
# =============================================================================
DASHBOARD_PORT = 8081  # Changed from 8080 due to System process holding port
HEALTH_URL = f"http://localhost:{DASHBOARD_PORT}/health"
HEALTH_DEEP_URL = f"http://localhost:{DASHBOARD_PORT}/health/deep"

# councilctl.py location - server.py should be in same directory
SERVER_SCRIPT = Path(__file__).parent / "server.py"

# Secure PID file location (user-owned directory, not shared /tmp)
if platform.system() == 'Windows':
    PID_DIR = Path(os.environ.get('LOCALAPPDATA', '')) / 'Council'
else:
    PID_DIR = Path.home() / '.local' / 'state' / 'council'

PID_FILE = PID_DIR / 'dashboard.pid'
SHUTDOWN_TIMEOUT = 10  # seconds to wait for graceful shutdown


# =============================================================================
# PID FILE MANAGEMENT
# =============================================================================
def ensure_pid_dir() -> None:
    """Create PID directory with secure permissions."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    if platform.system() != 'Windows':
        # Unix: owner-only permissions
        os.chmod(PID_DIR, 0o700)


def read_pid() -> Optional[int]:
    """
    Read PID from file, return None if invalid or process doesn't exist.

    Returns:
        PID if valid and running, None otherwise
    """
    if not PID_FILE.exists():
        return None

    try:
        pid_str = PID_FILE.read_text().strip()
        pid = int(pid_str)

        # Verify process actually exists
        if platform.system() == 'Windows':
            import ctypes
            import ctypes.wintypes

            # Windows: use OpenProcess to check if PID exists
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFO = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFO, False, pid)

            if handle:
                kernel32.CloseHandle(handle)
                return pid
        else:
            # POSIX: use signal 0 to check if process exists
            os.kill(pid, 0)
            return pid

    except (ValueError, OSError, ProcessLookupError):
        # PID file invalid or process doesn't exist
        PID_FILE.unlink(missing_ok=True)
        return None


def write_pid(pid: int) -> None:
    """
    Write PID to file atomically.

    Uses temp file + rename pattern for atomicity (POSIX rename is atomic).
    On Windows, this is still safer than direct write for concurrent access.
    """
    ensure_pid_dir()
    temp_file = PID_FILE.with_suffix('.tmp')
    temp_file.write_text(str(pid))
    temp_file.replace(PID_FILE)  # Atomic on POSIX, safe on Windows


def clear_pid() -> None:
    """Remove PID file if it exists."""
    PID_FILE.unlink(missing_ok=True)


# =============================================================================
# HEALTH CHECKS
# =============================================================================
def check_health(timeout: int = 5) -> Optional[dict]:
    """
    Query health endpoint, return response or None.

    Args:
        timeout: Request timeout in seconds

    Returns:
        JSON response dict if successful, None otherwise
    """
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
        return None


def check_deep_health(timeout: int = 5) -> Optional[dict]:
    """
    Query deep health endpoint (database connectivity).

    Args:
        timeout: Request timeout in seconds

    Returns:
        JSON response dict if successful, None otherwise
    """
    try:
        with urllib.request.urlopen(HEALTH_DEEP_URL, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
        return None


# =============================================================================
# COMMANDS
# =============================================================================
def cmd_start() -> int:
    """
    Start the dashboard server.

    Returns:
        0 on success, 1 on failure
    """
    # Check if already running
    existing_pid = read_pid()
    if existing_pid:
        health = check_health()
        if health:
            print(f"✓ Dashboard already running (PID {existing_pid})")
            print(f"  Uptime: {health.get('uptime_seconds', 0):.0f}s")
            return 0
        else:
            print(f"⚠ Stale PID {existing_pid}, cleaning up...")
            clear_pid()

    # Verify server script exists
    if not SERVER_SCRIPT.exists():
        print(f"✗ Server script not found: {SERVER_SCRIPT}")
        return 1

    print(f"Starting dashboard on port {DASHBOARD_PORT}...")

    # Start detached process
    if platform.system() == 'Windows':
        # Windows: use CREATE_NEW_PROCESS_GROUP for isolation
        # DETACHED_PROCESS prevents inheriting parent's console
        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    else:
        # POSIX: use start_new_session to create process group
        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    write_pid(proc.pid)

    # Wait for health check (with timeout)
    print(f"Started with PID {proc.pid}, waiting for health check...")
    for i in range(10):  # 5 seconds total
        time.sleep(0.5)
        health = check_health(timeout=1)
        if health:
            print(f"✓ Dashboard started (PID {proc.pid})")
            print(f"  → http://localhost:{DASHBOARD_PORT}")
            return 0

    print(f"✗ Dashboard failed health check (check logs)")
    return 1


def cmd_stop() -> int:
    """
    Graceful shutdown - sends SIGTERM, waits for cleanup, then force-kills.

    Returns:
        0 on success, 1 on failure
    """
    pid = read_pid()
    if not pid:
        print("Dashboard not running (no PID file)")
        # Try to stop by health check anyway
        health = check_health(timeout=1)
        if not health:
            return 0
        print("⚠ Found running dashboard but no PID file")

    print(f"Stopping dashboard (PID {pid})...")

    # Send graceful shutdown signal
    try:
        if platform.system() == 'Windows':
            # Windows: CTRL_BREAK_EVENT to process group
            # Note: Python needs to set CTRL_C_EVENT handler for this to work
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            # POSIX: SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
    except OSError as e:
        print(f"  Warning: signal failed: {e}")

    # Wait for graceful shutdown (WAL checkpoint takes ~100-500ms)
    print(f"  Waiting for graceful shutdown (max {SHUTDOWN_TIMEOUT}s)...")
    for i in range(SHUTDOWN_TIMEOUT * 2):  # Check every 0.5s
        time.sleep(0.5)
        health = check_health(timeout=1)
        if not health:
            print("✓ Dashboard stopped gracefully")
            clear_pid()
            return 0

    # Force kill if necessary
    print("⚠ Graceful shutdown timed out, forcing...")
    try:
        if platform.system() == 'Windows':
            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                          capture_output=True, timeout=5)
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass

    clear_pid()
    print("✓ Dashboard terminated")
    return 0


def cmd_status() -> int:
    """
    Check dashboard status - reports actual health, not just PID.

    Returns:
        0 if healthy, 1 if unhealthy or not running
    """
    pid = read_pid()
    if not pid:
        print("✗ Dashboard not running")
        return 1

    health = check_health()
    if health:
        print(f"✓ Dashboard healthy (PID {pid})")
        print(f"  Uptime: {health.get('uptime_seconds', 0):.0f}s")

        # Optional: check deep health (database)
        deep_health = check_deep_health(timeout=2)
        if deep_health:
            db_status = deep_health.get('database', 'unknown')
            wal_mode = deep_health.get('wal_mode', False)
            print(f"  Database: {db_status}, WAL: {wal_mode}")
        return 0
    else:
        print(f"⚠ Dashboard process exists (PID {pid}) but not responding")
        return 1


def cmd_cleanup() -> int:
    """
    Find and kill orphaned council-related processes.

    Uses psutil to find processes by command line inspection.

    Returns:
        0 on success, 1 if psutil not available
    """
    try:
        import psutil
    except ImportError:
        print("Install psutil for cleanup: pip install psutil")
        return 1

    current_pid = os.getpid()
    legitimate_pid = read_pid()
    killed = 0

    print("Scanning for orphaned council processes...")

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid in (current_pid, legitimate_pid):
                # Skip current process and legitimate dashboard
                continue

            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline)

            # Check if this is a council-related process
            if 'server.py' in cmdline_str or 'councilctl.py' in cmdline_str:
                print(f"  Killing orphan: PID {proc.pid} ({proc.info['name']})")
                proc.terminate()
                killed += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print(f"✓ Cleaned up {killed} orphaned process(es)")
    return 0


def cmd_restart() -> int:
    """
    Restart dashboard - stop then start.

    Returns:
        0 on success, 1 on failure
    """
    cmd_stop()
    time.sleep(1)
    return cmd_start()


def cmd_debug() -> int:
    """
    Launch browser with DevTools for troubleshooting (Condition 3).

    Creates isolated temporary profile, auto-opens DevTools,
    cleans up profile on exit.

    Returns:
        0 on success, 1 on failure
    """
    # First, ensure dashboard is running
    health = check_health(timeout=2)
    if not health:
        print("Dashboard not running. Start it first: councilctl start")
        return 1

    print("Launching diagnostic browser session...")

    # Find Chrome executable
    chrome_paths = [
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        os.path.expandvars(r'%PROGRAMFILES%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    ]

    chrome_path = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_path = path
            break

    # Check PATH as fallback
    if not chrome_path:
        for path_dir in os.environ.get('PATH', '').split(os.pathsep):
            for chrome_name in ['chrome', 'google-chrome', 'chromium']:
                test_path = os.path.join(path_dir, chrome_name)
                if os.path.exists(test_path):
                    chrome_path = test_path
                    break
            if chrome_path:
                break

    if not chrome_path:
        print("Chrome not found. Install Chrome or set CHROME_PATH environment variable")
        return 1

    # Create isolated user data directory (prevents profile contamination)
    debug_profile = tempfile.mkdtemp(prefix='council_debug_')

    # Build Chrome args for secure debugging
    # NOTE: No --remote-debugging-port - RCE risk per Council security review
    # Uses --auto-open-devtools-for-tabs for local debugging only
    chrome_args = [
        chrome_path,
        f'--user-data-dir={debug_profile}',
        '--auto-open-devtools-for-tabs',  # Open DevTools automatically
        '--disable-extensions',            # No extensions in debug session
        '--disable-plugins',               # No plugins
        '--incognito',                     # Ephemeral session (doesn't save to profile)
        '--no-first-run',
        '--no-default-browser-check',
        f'http://localhost:{DASHBOARD_PORT}/'
    ]

    print(f"  Profile: {debug_profile}")
    print(f"  Opening: http://localhost:{DASHBOARD_PORT}/")
    print("  DevTools will open automatically. Press Ctrl+C when done.")

    try:
        proc = subprocess.Popen(chrome_args)
        proc.wait()  # Wait for browser to close
    except KeyboardInterrupt:
        print("\nClosing debug session...")
        proc.terminate()
        proc.wait(timeout=5)
    finally:
        # Cleanup temporary profile
        try:
            shutil.rmtree(debug_profile)
            print("  ✓ Cleaned up debug profile")
        except Exception as e:
            print(f"  ⚠ Warning: Could not cleanup profile: {e}")

    return 0


# =============================================================================
# MAIN
# =============================================================================
COMMANDS = {
    'start': cmd_start,
    'stop': cmd_stop,
    'restart': cmd_restart,
    'status': cmd_status,
    'cleanup': cmd_cleanup,
    'debug': cmd_debug,
}


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Council Dashboard Control CLI")
        print("=" * 50)
        print("\nUsage:")
        for cmd_name in COMMANDS:
            print(f"  councilctl {cmd_name}")
        print("\nPer Council Decree: Resource Awareness Implementation")
        print("=" * 50)
        return 1

    command = sys.argv[1]
    return COMMANDS[command]()


if __name__ == '__main__':
    sys.exit(main())
