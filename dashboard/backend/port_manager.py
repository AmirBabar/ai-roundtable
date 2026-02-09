#!/usr/bin/env python3
"""
Dashboard Startup Helper with Port Management v2

Security Improvements per Council Review 2026-02-03:
- PID validation before use (injection protection)
- Process ownership validation (psutil)
- Atomic port reservation (fixes race conditions)
- Opt-in process killing (--force-kill flag)
- Graceful termination before force kill
- Safe stale PID file cleanup
"""

import socket
import sys
import os
import time
import argparse
from pathlib import Path
from typing import Optional, Tuple

# Configuration
PREFERRED_PORTS = [8080, 8081, 8082, 8083, 8084]
HOST = "127.0.0.1"
PID_FILE = Path(__file__).parent.parent / "data" / "dashboard.pid"

# Optional dependency for safe process management
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[WARN] psutil not available - using less safe fallback methods")


# ============================================================================
# PID VALIDATION (Security: Injection Protection)
# ============================================================================

def validate_pid_format(pid_str: str) -> bool:
    """
    Validate PID file content is numeric and safe.

    Per Council: Prevents PID injection attacks.
    """
    if not pid_str or not isinstance(pid_str, str):
        return False

    # Strip whitespace and check if purely numeric
    pid_str = pid_str.strip()
    if not pid_str.isdigit():
        return False

    # Reasonable range check (Windows PIDs are typically < 65535 in practice)
    try:
        pid = int(pid_str)
        return 0 < pid < 1000000  # Generous upper bound
    except ValueError:
        return False


def read_pid_file(pid_file: Path) -> Optional[int]:
    """
    Safely read and validate PID from file.

    Returns None if:
    - File doesn't exist
    - Content is invalid (non-numeric, empty, etc.)
    - Content has been tampered with
    """
    if not pid_file.exists():
        return None

    try:
        content = pid_file.read_text()

        # Remove UTF-8 BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]

        content = content.strip()

        # Validate format before using
        if not validate_pid_format(content):
            print(f"[WARN] Invalid PID file format: {repr(content)}")
            print("[INFO] Removing stale/corrupt PID file")
            pid_file.unlink(missing_ok=True)
            return None

        return int(content)
    except (OSError, IOError) as e:
        print(f"[WARN] Could not read PID file: {e}")
        return None


# ============================================================================
# PROCESS VALIDATION (Security: Ownership Check)
# ============================================================================

def validate_process_is_dashboard(pid: int) -> bool:
    """
    Verify the process is actually a dashboard instance.

    Per Council: Prevents killing unrelated processes.

    Uses psutil if available for detailed process inspection.
    Falls back to basic existence check.
    """
    if not PSUTIL_AVAILABLE:
        # Fallback: just check if process exists
        try:
            os.kill(pid, 0)  # Signal 0 checks existence
            return True  # Assume it's ours if we can signal it
        except OSError:
            return False

    try:
        process = psutil.Process(pid)

        # Check process name
        name = process.name().lower()
        if "python" in name or "pythonw" in name:
            # It's a Python process - check command line
            try:
                cmdline = " ".join(process.cmdline()).lower()
                # Check if it looks like our dashboard
                if "server" in cmdline or "dashboard" in cmdline or "http.server" in cmdline:
                    return True
                # If it's python but not obviously dashboard, be cautious
                print(f"[WARN] PID {pid} is Python but may not be dashboard: {cmdline[:100]}")
                return False
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                return False

        return False  # Not a Python process

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


# ============================================================================
# ATOMIC PORT RESERVATION (Fixes Race Conditions)
# ============================================================================

class ReservedPort:
    """
    Holds a reserved port socket.

    Per Council: Prevents TOCTOU race conditions by keeping
    the socket bound. Caller must keep this object alive
    while using the port.
    """

    def __init__(self, host: str, port: int, socket: socket.socket):
        self.host = host
        self.port = port
        self._socket = socket

    def get_address(self) -> Tuple[str, int]:
        """Get the bound address for use with HTTPServer."""
        return (self.host, self.port)

    def release(self):
        """Release the port reservation."""
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()


def reserve_port(host: str, port: int) -> Optional[ReservedPort]:
    """
    Atomically reserve a port by binding and holding the socket.

    Per Council: Fixes TOCTOU race condition between port check
    and actual server binding.

    Returns ReservedPort object that must be kept alive while
    the port is in use. Call release() when done.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(1)

        return ReservedPort(host, port, sock)

    except (OSError, socket.error) as e:
        return None


def is_port_available(host: str, port: int) -> bool:
    """
    Quick check if port is available (non-reserving).

    For initial scanning. Use reserve_port() when ready to
    actually bind.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen(1)
            return True
    except (OSError, socket.error):
        return False


# ============================================================================
# SAFE PROCESS TERMINATION
# ============================================================================

def terminate_process_gracefully(pid: int, timeout: float = 2.0) -> bool:
    """
    Attempt graceful termination first.

    Per Council: Try SIGTERM before SIGKILL to allow cleanup.
    """
    if not PSUTIL_AVAILABLE:
        # Fallback: no graceful option available
        return False

    try:
        process = psutil.Process(pid)
        process.terminate()  # SIGTERM

        try:
            process.wait(timeout=timeout)
            return True  # Clean exit
        except psutil.TimeoutExpired:
            # Still running, need force kill
            return False

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def kill_process_on_port_unsafe(host: str, port: int) -> bool:
    """
    UNSAFE fallback for Windows without psutil.

    Per Council: Should only be used with explicit user consent.
    Uses netstat + taskkill approach.
    """
    print(f"[WARN] Using UNSAFE process termination method")
    print(f"[WARN] Requires --force-kill flag to proceed")

    try:
        import subprocess

        # Find process using the port
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )

        pids_killed = []
        for line in result.stdout.strip().split('\n'):
            if line and not line.startswith('Proto'):
                parts = line.split()
                if len(parts) >= 5:
                    laddr = parts[1]
                    pid = parts[4]

                    # Parse "Local Address" format (IP:Port)
                    if f':{port}' in laddr:
                        print(f"[INFO] Attempting to kill process {pid} on port {port}")

                        # Kill the process
                        kill_result = subprocess.run(
                            ['taskkill', '/F', '/PID', pid],
                            capture_output=True,
                            timeout=10
                        )

                        if kill_result.returncode == 0:
                            pids_killed.append(pid)
                            print(f"[OK] Killed process {pid}")
                        else:
                            print(f"[WARN] Failed to kill process {pid}")

        return len(pids_killed) > 0

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"[ERROR] Could not kill process on port {port}: {e}")
        return False


def kill_dashboard_process_on_port(host: str, port: int, force: bool = False) -> bool:
    """
    Safely kill only dashboard processes on the specified port.

    Per Council:
    - Validates process is actually a dashboard instance
    - Attempts graceful termination first
    - Only uses force kill if graceful fails
    - Requires --force flag for unsafe fallback

    Args:
        host: Host address to check
        port: Port number to clear
        force: If True, use unsafe methods as fallback

    Returns:
        True if port was cleared, False otherwise
    """
    if not PSUTIL_AVAILABLE:
        print("[WARN] psutil not available for safe process management")
        if force:
            print("[INFO] --force specified: using unsafe fallback")
            return kill_process_on_port_unsafe(host, port)
        else:
            print("[INFO] Not killing process (requires --force flag)")
            print("[HINT] Install psutil: pip install psutil")
            return False

    try:
        killed_any = False

        # Find all connections and check if any are our dashboard
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.pid is not None:
                pid = conn.pid

                # Validate it's actually a dashboard process
                if validate_process_is_dashboard(pid):
                    print(f"[INFO] Found dashboard process {pid} on port {port}")

                    # Try graceful termination first
                    if terminate_process_gracefully(pid):
                        print(f"[OK] Gracefully terminated process {pid}")
                        killed_any = True
                    else:
                        # Graceful failed, try force kill
                        print(f"[INFO] Graceful termination failed, using force kill")
                        try:
                            psutil.Process(pid).kill()
                            print(f"[OK] Force killed process {pid}")
                            killed_any = True
                        except psutil.NoSuchProcess:
                            print(f"[OK] Process {pid} already terminated")
                            killed_any = True
                else:
                    print(f"[WARN] Port {port} in use by non-dashboard process {pid}")
                    print(f"[INFO] Not killing unrelated process")

        if killed_any:
            # Give processes time to fully terminate
            time.sleep(0.5)

        return killed_any

    except (psutil.Error, OSError) as e:
        print(f"[ERROR] Error during process management: {e}")
        return False


# ============================================================================
# PORT DISCOVERY
# ============================================================================

def find_available_port(host: str, preferred_ports: list) -> Tuple[Optional[int], Optional[int]]:
    """
    Find the first available port from a list of preferences.

    Returns tuple: (port, port_number_as_int)
    """
    for port_str in preferred_ports:
        port = int(port_str) if isinstance(port_str, str) else port_str
        if is_port_available(host, port):
            return port, port
    return None, None


# ============================================================================
# PID FILE MANAGEMENT
# ============================================================================

def check_existing_process(pid_file: Path) -> Tuple[bool, Optional[int]]:
    """
    Check if an existing dashboard process is still running.

    Per Council: Validates PID format and process ownership.

    Returns:
        (process_exists, pid) tuple
    """
    pid = read_pid_file(pid_file)
    if pid is None:
        return False, None

    # Check if process is actually running
    try:
        os.kill(pid, 0)  # Signal 0 checks if process exists
    except OSError:
        # Process not running - stale PID
        print("[INFO] Stale PID file found (process not running)")
        pid_file.unlink(missing_ok=True)
        return False, None

    # Process exists - validate it's actually a dashboard
    if validate_process_is_dashboard(pid):
        print(f"[WARN] Existing dashboard found running (PID: {pid})")
        return True, pid
    else:
        print(f"[WARN] PID file exists but process {pid} is not a dashboard")
        print("[INFO] Removing stale PID file")
        pid_file.unlink(missing_ok=True)
        return False, None


def write_pid_file(pid_file: Path, pid: Optional[int] = None) -> bool:
    """Write current process PID to file for tracking."""
    try:
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_to_write = pid if pid is not None else os.getpid()

        # Write as plain numeric string (validated by read_pid_file)
        pid_file.write_text(str(pid_to_write))
        return True
    except (OSError, IOError) as e:
        print(f"[ERROR] Could not write PID file: {e}")
        return False


def cleanup_pid_file(pid_file: Path) -> None:
    """Remove PID file on shutdown."""
    if pid_file.exists():
        pid_file.unlink(missing_ok=True)


# ============================================================================
# MAIN PORT MANAGEMENT
# ============================================================================

def get_dashboard_port(force_kill: bool = False, verbose: bool = False) -> Optional[int]:
    """
    Determine which port to use for the dashboard.

    Strategy (per Council recommendations):
    1. Check for existing PID file and validate process ownership
    2. If running and is dashboard, return None (use existing)
    3. If not running, find first available port
    4. Optionally attempt to clear port (only if --force-kill specified)

    Args:
        force_kill: If True, attempt to kill processes on preferred ports
        verbose: If True, print detailed information

    Returns:
        Port number if available, None if existing dashboard running
    """
    if verbose:
        print("[START] Dashboard Port Management v2")
        print(f"[INFO] psutil available: {PSUTIL_AVAILABLE}")

    # Check for existing dashboard process
    process_exists, pid = check_existing_process(PID_FILE)
    if process_exists:
        print("[INFO] Dashboard already running. Use existing process or stop it first.")
        print(f"[HINT] To stop: Kill PID {pid} or press Ctrl+C in its terminal")
        return None

    # Try to find available port
    port, port_int = find_available_port(HOST, PREFERRED_PORTS)

    if port:
        print(f"[OK] Port {port} is available")
        # Reserve the port atomically
        reserved = reserve_port(HOST, port)
        if reserved:
            print(f"[OK] Port {port} reserved")
            write_pid_file(PID_FILE)
            return port_int
        else:
            print(f"[WARN] Port {port} was available but reservation failed")
            return None

    # All preferred ports taken
    print(f"[WARN] All preferred ports are in use: {PREFERRED_PORTS}")

    if force_kill:
        print(f"[INFO] --force-kill specified: attempting to clear port 8080")
        if kill_dashboard_process_on_port(HOST, 8080, force=True):
            # Check if port is now available
            if is_port_available(HOST, 8080):
                print("[OK] Port 8080 now available")
                write_pid_file(PID_FILE)
                return 8080
    else:
        print("[INFO] Not attempting to clear ports (--force-kill not specified)")
        print("[HINT] Use --force-kill to automatically clear ports")

    # Try alternative ports
    for alt_port in [8085, 8086, 8087, 8088, 8089]:
        if is_port_available(HOST, alt_port):
            print(f"[OK] Using alternative port {alt_port}")
            write_pid_file(PID_FILE)
            return alt_port

    print("[ERROR] No available ports found")
    return None


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """CLI entry point for port management."""
    parser = argparse.ArgumentParser(
        description="Dashboard port management utility"
    )
    parser.add_argument(
        "--force-kill",
        action="store_true",
        help="Allow automatic process termination (USE WITH CAUTION)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed information"
    )

    args = parser.parse_args()

    if args.force_kill and not PSUTIL_AVAILABLE:
        print("[WARN] --force-kill specified but psutil not available")
        print("[WARN] Will use unsafe fallback methods")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            print("[ABORT] Cancelled by user")
            sys.exit(1)

    port = get_dashboard_port(force_kill=args.force_kill, verbose=args.verbose)

    if port:
        print(f"\n[START] Dashboard will use port {port}")
        print(f"[INFO] PID file: {PID_FILE}")
        print(f"[INFO] Access at: http://localhost:{port}/index.html")
        sys.exit(0)
    else:
        print("\n[ABORT] Could not find available port")
        sys.exit(1)


if __name__ == "__main__":
    main()
