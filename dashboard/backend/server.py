#!/usr/bin/env python3
"""
Council Observability Dashboard - HTTP Server
Python implementation for reliable background execution

Per Council decree ARCH-2024-008

FEATURES:
- Real-time SSE events for API calls
- Budget alert system
- Metrics, health, and export endpoints
"""

import http.server
import socketserver
import sqlite3
import json
import os
import uuid
import threading
import time
import signal
import sys
from datetime import datetime, timedelta
from queue import Queue
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================
PORT_DEFAULT = 8081  # Fallback if port discovery fails
HOST = "127.0.0.1"
DATABASE_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"
FRONTEND_PATH = Path(__file__).parent.parent / "frontend"
TOKEN_PATH = Path(__file__).parent.parent / "data" / ".auth-token"

# Dynamic port (will be set by port_manager if available)
PORT = PORT_DEFAULT

# Server start time for health endpoint uptime tracking
SERVER_START_TIME = time.time()

# Rate limiting (per Council decree: 10 req/10s)
rate_tracker = {}
rate_lock = threading.Lock()

# ============================================================================
# IMPORT NEW MODULES
# ============================================================================
try:
    from sse_events import get_sse_manager, generate_client_id, client_event_generator, format_sse_line
    from budget_alerts import get_budget_status, get_spending_breakdown, acknowledge_alert, check_budget_thresholds, set_budget_threshold
    SSE_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] SSE/Budget modules not available: {e}")
    SSE_AVAILABLE = False

try:
    from gateway_logs import get_recent_logs, tail_logs_stream, get_log_stats, ensure_log_directory
    GATEWAY_LOGS_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Gateway logs module not available: {e}")
    GATEWAY_LOGS_AVAILABLE = False

# Port manager for dynamic port discovery
try:
    from port_manager import get_dashboard_port, write_pid_file, cleanup_pid_file
    PORT_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Port manager not available: {e}")
    PORT_MANAGER_AVAILABLE = False

# ============================================================================
# CONFIG MANAGEMENT (Per Council Diamond Debate 2026-02-07)
# ============================================================================
try:
    from auth import config_auth, require_config_auth
    from secret_manager import secret_manager
    from config_validator import config_validator, ValidationResult
    from config_io import config_file_manager
    CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Config modules not available: {e}")
    CONFIG_AVAILABLE = False

# ============================================================================
# AUTH TOKEN
# ============================================================================
def get_auth_token():
    """Get or generate auth token"""
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()

    token = str(uuid.uuid4())
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token)
    print(f"[SECURITY] Generated new auth token: {token}")
    print(f"[SECURITY] Token saved to: {TOKEN_PATH}")
    return token

AUTH_TOKEN = get_auth_token()

# ============================================================================
# RATE LIMITING
# ============================================================================
def check_rate_limit(client_ip: str) -> bool:
    """Check if request is within rate limit"""
    now = time.time()
    window_start = now - 10

    with rate_lock:
        # Clean old entries
        old_keys = [k for k, v in rate_tracker.items() if v < window_start]
        for k in old_keys:
            del rate_tracker[k]

        # Count requests from this IP
        count = sum(1 for k, v in rate_tracker.items()
                   if k.startswith(f"{client_ip}-") and v >= window_start)

        if count >= 10:
            return False

        # Track this request
        rate_tracker[f"{client_ip}-{now}"] = now
        return True

# ============================================================================
# DATABASE
# ============================================================================
def execute_query(query: str, params: dict = None) -> list:
    """Execute SQL query and return results"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if params:
            cursor.execute(query, list(params.values()))
        else:
            cursor.execute(query)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        conn.close()
        return result
    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        return [{"error": str(e)}]

# ============================================================================
# GRACEFUL SHUTDOWN (Per Council Decree: Resource Awareness)
# ============================================================================
def graceful_shutdown(signum: int, frame):
    """
    Handle SIGTERM/SIGINT gracefully with WAL checkpoint.

    This is CRITICAL for preventing SQLite WAL corruption when the
    server is terminated. Called by signal handlers on shutdown.
    """
    print(f"\n[SHUTDOWN] Received signal {signum}, cleaning up...")

    # Checkpoint WAL to prevent corruption
    try:
        conn = sqlite3.connect(str(DATABASE_PATH), timeout=5)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        print("[SHUTDOWN] Database WAL checkpoint complete")
    except Exception as e:
        print(f"[SHUTDOWN] Warning: WAL checkpoint failed: {e}")

    # Shutdown SSE manager if available
    if SSE_AVAILABLE:
        try:
            from sse_events import get_sse_manager
            get_sse_manager().shutdown()
            print("[SHUTDOWN] SSE manager shutdown complete")
        except Exception as e:
            print(f"[SHUTDOWN] Warning: SSE shutdown failed: {e}")

    print("[SHUTDOWN] Server shutdown complete")
    sys.exit(0)


# Register signal handlers at module load (main thread only)
# Windows: SIGINT works, SIGTERM may not be delivered reliably
# POSIX: Both SIGTERM and SIGINT work as expected
signal.signal(signal.SIGINT, graceful_shutdown)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, graceful_shutdown)


# ============================================================================
# TIME RANGE VALIDATION (per Council decree)
# ============================================================================
def get_time_range_seconds(range_param: str) -> int:
    """Convert time range parameter to seconds"""
    allowlist = {
        "all": 0,  # Special case: all time
        "24h": 86400,
        "7d": 604800,
        "30d": 2592000,
    }
    return allowlist.get(range_param, allowlist["24h"])

# ============================================================================
# API HANDLERS
# ============================================================================
def send_json(response, data: dict, status: int = 200):
    """Send JSON response"""
    response.send_response(status)
    response.send_header("Content-Type", "application/json")
    response.send_header("Access-Control-Allow-Origin", "*")
    response.send_header("Cache-Control", "no-cache, no-store")
    response.end_headers()
    response.wfile.write(json.dumps(data).encode())

def send_file(response, filepath: Path):
    """Send static file"""
    if not filepath.exists():
        send_json(response, {"error": "Not found"}, 404)
        return

    ext = filepath.suffix
    content_types = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    response.send_response(200)
    response.send_header("Content-Type", content_types.get(ext, "application/octet-stream"))
    response.send_header("Access-Control-Allow-Origin", "*")

    # Cache static assets
    if ext in [".css", ".js"]:
        response.send_header("Cache-Control", "max-age=3600")

    response.end_headers()
    response.wfile.write(filepath.read_bytes())

def check_auth(request) -> bool:
    """Check request authentication"""
    # Check query string - parse properly from request path
    parsed = urlparse(request.path)
    query = parse_qs(parsed.query)
    if "token" in query and query["token"][0] == AUTH_TOKEN:
        return True

    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header.split()) > 1:
        if auth_header.split()[1] == AUTH_TOKEN:
            return True

    return False


# ============================================================================
# HEALTH ENDPOINTS (Per Council Decree: Resource Awareness)
# ============================================================================
def handle_health_check(request, response):
    """
    Handle /health endpoint - lightweight check for watchdog monitoring.

    Returns:
        - status: "healthy" if server is running
        - pid: server process ID
        - uptime_seconds: time since server started
        - timestamp: ISO format current time

    No authentication required - this is for process monitoring.
    Call frequently (every 10s) for watchdog.
    """
    response.send_response(200)
    response.send_header("Content-Type", "application/json")
    response.send_header("Access-Control-Allow-Origin", "*")
    response.end_headers()

    health_data = {
        "status": "healthy",
        "pid": os.getpid(),
        "uptime_seconds": time.time() - SERVER_START_TIME,
        "timestamp": datetime.now().isoformat()
    }
    response.wfile.write(json.dumps(health_data).encode())


def handle_deep_health_check(request, response):
    """
    Handle /health/deep endpoint - database connectivity check.

    Returns:
        - status: "healthy" or "unhealthy"
        - database: "connected" if DB accessible
        - wal_mode: True if WAL is enabled
        - timestamp: ISO format current time

    No authentication required - this is for process monitoring.
    Call sparingly (once per minute) as it opens a DB connection.
    """
    try:
        conn = sqlite3.connect(str(DATABASE_PATH), timeout=5)
        cursor = conn.execute("SELECT 1")
        cursor.fetchone()

        # Check WAL mode
        wal_result = conn.execute("PRAGMA journal_mode").fetchone()
        wal_mode = wal_result and wal_result[0].lower() == "wal"

        conn.close()

        response.send_response(200)
        response.send_header("Content-Type", "application/json")
        response.send_header("Access-Control-Allow-Origin", "*")
        response.end_headers()

        health_data = {
            "status": "healthy",
            "database": "connected",
            "wal_mode": wal_mode,
            "timestamp": datetime.now().isoformat()
        }
        response.wfile.write(json.dumps(health_data).encode())

    except Exception as e:
        response.send_response(503)
        response.send_header("Content-Type", "application/json")
        response.send_header("Access-Control-Allow-Origin", "*")
        response.end_headers()

        health_data = {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        response.wfile.write(json.dumps(health_data).encode())

def handle_metrics(request, response):
    """Handle /api/metrics endpoint"""
    query_params = parse_qs(urlparse(request.path).query)
    range_param = query_params.get("range", ["24h"])[0]
    after = query_params.get("after", [None])[0]

    seconds = get_time_range_seconds(range_param)

    # Use COALESCE to handle NULL case - get the latest timestamp or use 'now'
    if after:
        # If after parameter provided, get records after that timestamp
        where_clause = f"WHERE timestamp > '{after}'"
    elif seconds == 0:
        # "All Time" - no time filter, get all records
        where_clause = ""
    else:
        # Otherwise, get records from the last N seconds (use localtime to match tracker)
        where_clause = f"WHERE datetime(timestamp) >= datetime('now', 'localtime', '-{seconds} seconds')"

    # Build SQL query with optional WHERE clause
    if where_clause:
        sql = f"""
        SELECT timestamp, model, task_type, prompt_tokens, completion_tokens,
               total_tokens, cost_usd, duration_seconds, status
        FROM api_calls
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT 1000
        """
    else:
        sql = f"""
        SELECT timestamp, model, task_type, prompt_tokens, completion_tokens,
               total_tokens, cost_usd, duration_seconds, status
        FROM api_calls
        ORDER BY timestamp DESC
        LIMIT 1000
        """

    data = execute_query(sql)
    send_json(response, data)

def handle_health(request, response):
    """Handle /api/health endpoint"""
    # Get gateway status
    gateway_sql = """
        SELECT gateway_status, models_available, response_time_ms, timestamp as last_check
        FROM gateway_health
        ORDER BY timestamp DESC
        LIMIT 1
    """
    gateway = execute_query(gateway_sql)

    # Get today's summary (use localtime to match tracker timestamps)
    summary_sql = """
        SELECT COUNT(*) as total_calls,
               SUM(total_tokens) as total_tokens,
               SUM(cost_usd) as total_cost,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
               SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as error_count
        FROM api_calls
        WHERE date(timestamp) = date('now', 'localtime')
    """
    summary = execute_query(summary_sql)

    result = {
        "gateway": gateway[0] if gateway else None,
        "today": summary[0] if summary else None,
        "timestamp": datetime.now().isoformat()
    }
    send_json(response, result)

def handle_pricing(request, response):
    """Handle /api/pricing endpoint - return model pricing and tier estimates"""
    try:
        from pricing import MODEL_PRICING, COUNCIL_MODEL_ALIASES, TIER_COSTS, get_pricing
        from diamond_cost_predictor import DiamondCostPredictor

        # Get model pricing for all Council models
        model_pricing = {}
        for alias in COUNCIL_MODEL_ALIASES:
            pricing = get_pricing(alias)
            model_pricing[alias] = {
                "input_price_per_1m": pricing.input_price_per_1m,
                "output_price_per_1m": pricing.output_price_per_1m,
                "provider": pricing.provider,
            }

        # Get tier cost estimates
        tier_estimates = {}
        for tier_name, tier_data in TIER_COSTS.items():
            tier_estimates[tier_name] = {
                "name": tier_name,  # Use the tier_name itself
                "description": tier_data["description"],
                "models": tier_data["models"],
                "estimated_cost_range": tier_data["estimated_cost_range"],
                "typical_tokens": tier_data["typical_tokens"],
            }

        # Get current budget status
        budget_sql = """
            SELECT
                COALESCE(SUM(cost_usd), 0) as total_spend,
                COUNT(*) as total_calls
            FROM api_calls
            WHERE datetime(timestamp) >= datetime('now', 'localtime', 'start of month')
        """
        budget_data = execute_query(budget_sql)
        current_spend = budget_data[0]["total_spend"] if budget_data else 0

        result = {
            "model_pricing": model_pricing,
            "tier_estimates": tier_estimates,
            "current_monthly_spend": current_spend,
            "max_cost_per_query": 2.50,  # Council ruling
            "timestamp": datetime.now().isoformat()
        }
        send_json(response, result)
    except ImportError as e:
        send_json(response, {"error": f"Pricing module not available: {e}"}, status=503)

def handle_export(request, response):
    """Handle /api/export endpoint"""
    query_params = parse_qs(urlparse(request.path).query)
    format_param = query_params.get("format", ["json"])[0]
    range_param = query_params.get("range", ["24h"])[0]

    seconds = get_time_range_seconds(range_param)
    sql = f"""
        SELECT * FROM api_calls
        WHERE datetime(timestamp) >= datetime('now', 'localtime', '-{seconds} seconds')
        ORDER BY timestamp DESC
    """

    data = execute_query(sql)

    if format_param == "csv":
        response.send_response(200)
        response.send_header("Content-Type", "text/csv; charset=utf-8")
        response.send_header("Content-Disposition", "attachment; filename=dashboard-export.csv")
        response.end_headers()

        if data and "error" not in data[0]:
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            response.wfile.write(output.getvalue().encode())
        else:
            response.wfile.write(b"Error retrieving data")
    else:
        send_json(response, data)

def handle_sse_events(request, response):
    """Handle /api/events SSE endpoint for real-time updates"""
    if not SSE_AVAILABLE:
        send_json(response, {"error": "SSE not available"}, 503)
        return

    # Generate client ID and queue
    client_id = generate_client_id()
    event_queue = Queue()

    # Register with SSE manager
    sse_manager = get_sse_manager()
    sse_manager.add_client(client_id, event_queue)

    # Send SSE headers
    response.send_response(200)
    response.send_header("Content-Type", "text/event-stream")
    response.send_header("Cache-Control", "no-cache")
    response.send_header("Connection", "keep-alive")
    response.send_header("Access-Control-Allow-Origin", "*")
    response.send_header("X-Accel-Buffering", "no")  # Disable nginx buffering
    response.end_headers()

    # Stream events
    try:
        for event_data in client_event_generator(client_id, event_queue):
            response.wfile.write(event_data)
            response.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        # Client disconnected
        sse_manager.remove_client(client_id)
    except Exception as e:
        print(f"[SSE] Error streaming to client {client_id}: {e}")
        sse_manager.remove_client(client_id)

def handle_budget_status(request, response):
    """Handle /api/budget endpoint - get budget status and spending breakdown"""
    if not SSE_AVAILABLE:
        send_json(response, {"error": "Budget features not available"}, 503)
        return

    # Get budget status including spending breakdown and alerts
    status = get_budget_status()
    send_json(response, status)

def handle_set_budget(request, response):
    """Handle POST /api/budget endpoint - set budget threshold"""
    if not SSE_AVAILABLE:
        send_json(response, {"error": "Budget features not available"}, 503)
        return

    # Parse request body
    content_length = int(request.headers.get("Content-Length", 0))
    if content_length > 0:
        body = request.rfile.read(content_length)
        try:
            data = json.loads(body.decode('utf-8'))
            period = data.get("period")
            amount = data.get("amount")

            if period not in ["daily", "weekly", "monthly"]:
                send_json(response, {"error": "Invalid period. Use: daily, weekly, or monthly"}, 400)
                return

            if not isinstance(amount, (int, float)) or amount <= 0:
                send_json(response, {"error": "Invalid amount. Must be a positive number"}, 400)
                return

            # Set the threshold
            if set_budget_threshold(period, float(amount)):
                send_json(response, {
                    "success": True,
                    "period": period,
                    "threshold_usd": float(amount)
                })

                # Check if this new threshold creates alerts
                check_budget_thresholds()
            else:
                send_json(response, {"error": "Failed to set budget threshold"}, 500)
        except json.JSONDecodeError:
            send_json(response, {"error": "Invalid JSON"}, 400)
    else:
        send_json(response, {"error": "Missing request body"}, 400)

def handle_acknowledge_alert(request, response):
    """Handle POST /api/acknowledge-alert endpoint"""
    if not SSE_AVAILABLE:
        send_json(response, {"error": "Budget features not available"}, 503)
        return

    # Parse request body
    content_length = int(request.headers.get("Content-Length", 0))
    if content_length > 0:
        body = request.rfile.read(content_length)
        try:
            data = json.loads(body.decode('utf-8'))
            alert_id = data.get("alert_id")

            if not isinstance(alert_id, int) or alert_id <= 0:
                send_json(response, {"error": "Invalid alert_id"}, 400)
                return

            # Acknowledge the alert
            if acknowledge_alert(alert_id):
                send_json(response, {"success": True, "alert_id": alert_id})
            else:
                send_json(response, {"error": "Failed to acknowledge alert"}, 500)
        except json.JSONDecodeError:
            send_json(response, {"error": "Invalid JSON"}, 400)
    else:
        send_json(response, {"error": "Missing request body"}, 400)

# ============================================================================
# GATEWAY LOGS HANDLERS (Per Council Security Review 2026-02-01)
# ============================================================================
def handle_gateway_logs(request, response):
    """
    Handle GET /api/gateway-logs endpoint

    Query params:
    - lines: Number of recent log lines (default: 100)
    - level: Filter by level (ERROR, WARNING, INFO, DEBUG)
    - stream: If 'true', use SSE streaming (default: false)
    """
    if not GATEWAY_LOGS_AVAILABLE:
        send_json(response, {"error": "Gateway logs not available"}, 503)
        return

    parsed = urlparse(request.path)
    query = parse_qs(parsed.query)

    # Check if streaming requested
    stream = query.get('stream', ['false'])[0].lower() == 'true'

    if stream:
        # SSE streaming mode
        level_filter = query.get('level', [None])[0]

        # Set SSE headers
        response.send_response(200)
        response.send_header('Content-Type', 'text/event-stream')
        response.send_header('Cache-Control', 'no-cache')
        response.send_header('Connection', 'keep-alive')
        response.end_headers()

        # Stream logs
        try:
            for log_entry_json in tail_logs_stream(level_filter=level_filter):
                # Format as SSE event (format_sse_line already returns bytes)
                response.wfile.write(format_sse_line("log", log_entry_json))
                response.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected
            pass
    else:
        # Regular JSON response mode
        lines = int(query.get('lines', [100])[0])
        level_filter = query.get('level', [None])[0]

        logs = get_recent_logs(lines=lines, level_filter=level_filter)
        send_json(response, {"logs": logs, "count": len(logs)})

def handle_gateway_logs_stats(request, response):
    """Handle GET /api/gateway-logs/stats endpoint"""
    if not GATEWAY_LOGS_AVAILABLE:
        send_json(response, {"error": "Gateway logs not available"}, 503)
        return

    stats = get_log_stats()
    send_json(response, stats)


# ============================================================================
# COUNCIL MEMORY API ENDPOINTS
# ============================================================================
def handle_council_memory(request, response):
    """
    Handle GET /api/council-memory endpoint

    Returns Council Memory statistics, insights, sessions, and events.
    """
    try:
        from council_memory_api import handle_council_memory_request

        query_params = parse_qs(urlparse(request.path).query)
        result = handle_council_memory_request(query_params)
        send_json(response, result)
    except ImportError as e:
        send_json(response, {"error": f"Council Memory module not available: {e}"}, 503)
    except Exception as e:
        send_json(response, {"error": f"Council Memory query failed: {e}"}, 500)


def handle_council_sessions(request, response):
    """
    Handle GET /api/council-sessions endpoint

    Returns recent sessions from Council Memory.
    """
    try:
        from council_memory_api import handle_council_sessions_request

        query_params = parse_qs(urlparse(request.path).query)
        result = handle_council_sessions_request(query_params)
        send_json(response, result)
    except ImportError as e:
        send_json(response, {"error": f"Council Memory module not available: {e}"}, 503)
    except Exception as e:
        send_json(response, {"error": f"Council Memory query failed: {e}"}, 500)


# ============================================================================
# CONFIG MANAGEMENT API ENDPOINTS (Per Council Diamond Debate 2026-02-07)
# ============================================================================
def handle_config_get(request, response):
    """
    Handle GET /api/config endpoint - retrieve current configurations.

    Query params:
    - types: Comma-separated list of config types to fetch (default: all)
    - include_secrets: Include secret field previews (default: false)

    Returns combined config data with masked secrets.
    """
    if not CONFIG_AVAILABLE:
        send_json(response, {"error": "Config management not available"}, 503)
        return

    parsed = urlparse(request.path)
    query = parse_qs(parsed.query)
    types_param = query.get('types', ['litellm,council'])[0]
    include_secrets = query.get('include_secrets', ['false'])[0].lower() == 'true'

    types = types_param.split(',') if types_param else ['litellm', 'council']
    configs = {}
    warnings = []

    for config_type in types:
        success, data, error = config_file_manager.read_config(config_type)
        if success:
            # Process data to mask secrets if needed
            if include_secrets:
                configs[config_type] = data
            else:
                configs[config_type] = _mask_config_secrets(data, config_type)
        else:
            warnings.append(f"{config_type}: {error}")

    # Add any warnings from secret manager
    secret_warnings = secret_manager.get_warnings()
    warnings.extend(secret_warnings)

    result = {
        "configs": configs,
        "warnings": warnings if warnings else None,
        "timestamp": datetime.now().isoformat()
    }
    send_json(response, result)


def handle_config_post(request, response):
    """
    Handle POST /api/config endpoint - save configuration.

    Request body: JSON with 'type' and 'config' keys.
    Example: {"type": "litellm", "config": {...}}

    Validates before saving, creates backup, writes atomically.
    """
    if not CONFIG_AVAILABLE:
        send_json(response, {"error": "Config management not available"}, 503)
        return

    # Parse request body
    content_length = int(request.headers.get("Content-Length", 0))
    if content_length > 0:
        try:
            body = request.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            config_type = data.get('type')
            config_data = data.get('config')

            if not config_type:
                send_json(response, {"error": "Missing 'type' field"}, 400)
                return

            if config_type not in ['litellm', 'council']:
                send_json(response, {"error": f"Invalid config type: {config_type}"}, 400)
                return

            if not isinstance(config_data, dict):
                send_json(response, {"error": "Config must be an object"}, 400)
                return

            # Validate config before saving
            validation = config_validator.validate_config(config_type, config_data)
            if not validation.valid:
                send_json(response, {
                    "error": "Config validation failed",
                    "details": validation.errors,
                    "warnings": validation.warnings
                }, 400)
                return

            # Save config (with backup and atomic write)
            success, error = config_file_manager.write_config(config_type, config_data, validate=False)
            if success:
                send_json(response, {
                    "success": True,
                    "type": config_type,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                send_json(response, {"error": f"Failed to save config: {error}"}, 500)

        except json.JSONDecodeError:
            send_json(response, {"error": "Invalid JSON body"}, 400)
        except Exception as e:
            send_json(response, {"error": f"Save error: {str(e)}"}, 500)
    else:
        send_json(response, {"error": "Missing request body"}, 400)


def handle_config_schema(request, response):
    """
    Handle GET /api/config/schema endpoint - get JSON schema.

    Query params:
    - type: Config type ('litellm' or 'council')

    Returns the JSON schema for the specified config type.
    """
    if not CONFIG_AVAILABLE:
        send_json(response, {"error": "Config management not available"}, 503)
        return

    parsed = urlparse(request.path)
    query = parse_qs(parsed.query)
    config_type = query.get('type', ['litellm'])[0]

    if config_type not in ['litellm', 'council']:
        send_json(response, {"error": f"Invalid config type: {config_type}"}, 400)
        return

    schema = config_validator._schemas.get(config_type)
    if schema:
        send_json(response, {
            "schema": schema,
            "config_type": config_type
        })
    else:
        send_json(response, {"error": f"No schema found for: {config_type}"}, 404)


def handle_config_validate(request, response):
    """
    Handle POST /api/config/validate endpoint - validate without saving.

    Request body: JSON with 'type' and 'config' keys.
    Returns validation result without modifying files.
    """
    if not CONFIG_AVAILABLE:
        send_json(response, {"error": "Config management not available"}, 503)
        return

    content_length = int(request.headers.get("Content-Length", 0))
    if content_length > 0:
        try:
            body = request.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            config_type = data.get('type')
            config_data = data.get('config')

            if not config_type:
                send_json(response, {"error": "Missing 'type' field"}, 400)
                return

            if config_type not in ['litellm', 'council']:
                send_json(response, {"error": f"Invalid config type: {config_type}"}, 400)
                return

            # Validate config
            validation = config_validator.validate_config(config_type, config_data)

            result = {
                "valid": validation.valid,
                "errors": validation.errors if validation.errors else None,
                "warnings": validation.warnings if validation.warnings else None,
                "can_save": validation.valid
            }
            send_json(response, result)

        except json.JSONDecodeError:
            send_json(response, {"error": "Invalid JSON body"}, 400)
        except Exception as e:
            send_json(response, {"error": f"Validation error: {str(e)}"}, 500)
    else:
        send_json(response, {"error": "Missing request body"}, 400)


def handle_config_backups(request, response):
    """
    Handle GET /api/config/backups endpoint - list available backups.

    Query params:
    - type: Config type ('litellm' or 'council')

    Returns list of backup files for rollback.
    """
    if not CONFIG_AVAILABLE:
        send_json(response, {"error": "Config management not available"}, 503)
        return

    parsed = urlparse(request.path)
    query = parse_qs(parsed.query)
    config_type = query.get('type', ['litellm'])[0]

    if config_type not in ['litellm', 'council']:
        send_json(response, {"error": f"Invalid config type: {config_type}"}, 400)
        return

    backups = config_file_manager.list_backups(config_type)
    send_json(response, {
        "type": config_type,
        "backups": backups,
        "count": len(backups)
    })


def handle_config_revert(request, response):
    """
    Handle POST /api/config/revert endpoint - restore from backup.

    Request body: JSON with 'type' and 'backup' keys.
    Validates backup content before restoring.
    """
    if not CONFIG_AVAILABLE:
        send_json(response, {"error": "Config management not available"}, 503)
        return

    content_length = int(request.headers.get("Content-Length", 0))
    if content_length > 0:
        try:
            body = request.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            config_type = data.get('type')
            backup_filename = data.get('backup')

            if not config_type or not backup_filename:
                send_json(response, {"error": "Missing 'type' or 'backup' field"}, 400)
                return

            if config_type not in ['litellm', 'council']:
                send_json(response, {"error": f"Invalid config type: {config_type}"}, 400)
                return

            # Restore backup (with validation)
            success, error = config_file_manager.restore_backup(config_type, backup_filename)
            if success:
                send_json(response, {
                    "success": True,
                    "message": f"Restored from {backup_filename}",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                send_json(response, {"error": error}, 400)

        except json.JSONDecodeError:
            send_json(response, {"error": "Invalid JSON body"}, 400)
        except Exception as e:
            send_json(response, {"error": f"Revert error: {str(e)}"}, 500)
    else:
        send_json(response, {"error": "Missing request body"}, 400)


def _mask_config_secrets(config: dict, config_type: str) -> dict:
    """
    Recursively mask secret values in config for frontend display.

    This is a helper function that processes config data to ensure
    API keys and other secrets are never sent to the frontend.
    """
    if not isinstance(config, dict):
        return config

    masked = {}

    for key, value in config.items():
        if key == 'litellm_params' and isinstance(value, dict):
            # Special handling for litellm_params
            masked_params = {}
            for param_key, param_value in value.items():
                if param_key == 'api_key' and isinstance(param_value, str):
                    # Parse and mask API key
                    secret_ref = secret_manager.parse_secret_field(param_value, param_key)
                    masked_params[param_key] = secret_manager.serialize_for_frontend(secret_ref)
                else:
                    masked_params[param_key] = param_value
            masked[key] = masked_params

        elif key == 'general_settings' and isinstance(value, dict):
            # Handle general_settings.master_key
            masked_settings = {}
            for setting_key, setting_value in value.items():
                if setting_key == 'master_key' and isinstance(setting_value, str):
                    secret_ref = secret_manager.parse_secret_field(setting_value, setting_key)
                    masked_settings[setting_key] = secret_manager.serialize_for_frontend(secret_ref)
                else:
                    masked_settings[setting_key] = setting_value
            masked[key] = masked_settings

        elif isinstance(value, dict):
            masked[key] = _mask_config_secrets(value, config_type)
        elif isinstance(value, list):
            masked[key] = [
                _mask_config_secrets(item, config_type) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked[key] = value

    return masked


# ============================================================================
# HTTP REQUEST HANDLER
# ============================================================================
class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler for dashboard"""

    def __init__(self, *args, **kwargs):
        # Override frontend path
        self.directory = str(FRONTEND_PATH)
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        client_ip = self.client_address[0]

        # Debug logging
        self.log_message("GET request for path: %s", path)

        # Health endpoints - NO AUTH, NO RATE LIMIT (for watchdog monitoring)
        # Per Council decree: These must be callable by councilctl.py for process management
        # IMPORTANT: Check /health/deep BEFORE /health to avoid partial match
        if path == "/health/deep":
            self.log_message("Routing to /health/deep handler")
            handle_deep_health_check(self, self)
            return
        elif path == "/health":
            handle_health_check(self, self)
            return
        elif path == "/health/deep":
            handle_deep_health_check(self, self)
            return

        # Rate limiting (except for SSE endpoints which have their own management)
        if path not in ("/api/events", "/api/gateway-logs") and not check_rate_limit(client_ip):
            self.log_message("Rate limit exceeded for %s", client_ip)
            send_json(self, {"error": "Rate limit exceeded"}, 429)
            return

        # API endpoints require auth
        if path.startswith("/api/"):
            if not check_auth(self):
                self.log_message("Unauthorized request to %s", path)
                send_json(self, {"error": "Unauthorized"}, 401)
                return

            if path == "/api/metrics":
                handle_metrics(self, self)
            elif path == "/api/health":
                handle_health(self, self)
            elif path == "/api/pricing":
                handle_pricing(self, self)
            elif path == "/api/export":
                handle_export(self, self)
            elif path == "/api/events":
                handle_sse_events(self, self)
            elif path == "/api/budget":
                handle_budget_status(self, self)
            elif path == "/api/gateway-logs":
                handle_gateway_logs(self, self)
            elif path == "/api/gateway-logs/stats":
                handle_gateway_logs_stats(self, self)
            elif path == "/api/council-memory":
                handle_council_memory(self, self)
            elif path == "/api/council-sessions":
                handle_council_sessions(self, self)
            # Config management endpoints (specific paths first)
            elif path == "/api/config/schema":
                handle_config_schema(self, self)
            elif path == "/api/config/backups":
                handle_config_backups(self, self)
            elif path == "/api/config" or path.startswith("/api/config/"):
                handle_config_get(self, self)
            else:
                send_json(self, {"error": "Not found"}, 404)
        else:
            # Serve static files
            if path == "/" or path == "":
                path = "/index.html"

            filepath = FRONTEND_PATH / path.lstrip("/")
            send_file(self, filepath)

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        client_ip = self.client_address[0]

        # Rate limiting
        if not check_rate_limit(client_ip):
            self.log_message("Rate limit exceeded for %s", client_ip)
            send_json(self, {"error": "Rate limit exceeded"}, 429)
            return

        # API endpoints require auth
        if path.startswith("/api/"):
            if not check_auth(self):
                self.log_message("Unauthorized POST to %s", path)
                send_json(self, {"error": "Unauthorized"}, 401)
                return

            if path == "/api/budget":
                handle_set_budget(self, self)
            elif path == "/api/acknowledge-alert":
                handle_acknowledge_alert(self, self)
            # Config management endpoints
            elif path == "/api/config":
                handle_config_post(self, self)
            elif path == "/api/config/validate":
                handle_config_validate(self, self)
            elif path == "/api/config/revert":
                handle_config_revert(self, self)
            else:
                send_json(self, {"error": "Not found"}, 404)
        else:
            send_json(self, {"error": "Method not allowed"}, 405)

# ============================================================================
# MAIN SERVER
# ============================================================================
def main():
    """Start the dashboard server"""
    global PORT

    print("=" * 60)
    print("Council Observability Dashboard")
    print("=" * 60)

    # Dynamic port discovery
    if PORT_MANAGER_AVAILABLE:
        print("[INFO] Using dynamic port discovery...")
        discovered_port = get_dashboard_port(force_kill=False, verbose=True)
        if discovered_port:
            PORT = discovered_port
            print(f"[OK] Using dynamic port: {PORT}")
        else:
            print("[WARN] Port discovery failed, using fallback port")
            PORT = PORT_DEFAULT
    else:
        print(f"[INFO] Using configured port: {PORT}")

    # Auto-initialize database if missing
    if not DATABASE_PATH.exists():
        print("[WARN] Database not found, attempting auto-initialization...")
        try:
            import subprocess
            init_script = Path(__file__).parent / "lib" / "Initialize-DashboardDatabase.ps1"
            if init_script.exists():
                result = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(init_script)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    print("[OK] Database initialized successfully")
                else:
                    print(f"[ERROR] Database initialization failed: {result.stderr}")
                    return
            else:
                print(f"[ERROR] Initialization script not found: {init_script}")
                print("[HINT] Run Initialize-DashboardDatabase.ps1 manually")
                return
        except Exception as e:
            print(f"[ERROR] Auto-initialization failed: {e}")
            print("[HINT] Run Initialize-DashboardDatabase.ps1 manually")
            return

    print(f"Port: {PORT}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Frontend: {FRONTEND_PATH}")
    print(f"Auth Token: {AUTH_TOKEN}")
    if SSE_AVAILABLE:
        print("SSE Events: Enabled")
        print("Budget Alerts: Enabled")
    if GATEWAY_LOGS_AVAILABLE:
        print("Gateway Logs: Enabled")
    print("=" * 60)
    print(f"Server listening on http://{HOST}:{PORT}/")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    # Ensure log directory exists (per Council: Gateway Logs)
    if GATEWAY_LOGS_AVAILABLE:
        ensure_log_directory()

    # Register cleanup on exit
    import atexit
    if PORT_MANAGER_AVAILABLE:
        atexit.register(cleanup_pid_file)

    # Create server
    with socketserver.TCPServer((HOST, PORT), DashboardHandler) as httpd:
        httpd.allow_reuse_address = True

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] Server stopped")
            if SSE_AVAILABLE:
                get_sse_manager().shutdown()
            if PORT_MANAGER_AVAILABLE:
                cleanup_pid_file()

if __name__ == "__main__":
    main()
