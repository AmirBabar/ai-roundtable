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
from datetime import datetime, timedelta
from queue import Queue
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================
PORT = 8081
HOST = "127.0.0.1"
DATABASE_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"
FRONTEND_PATH = Path(__file__).parent.parent / "frontend"
TOKEN_PATH = Path(__file__).parent.parent / "data" / ".auth-token"

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
            else:
                send_json(self, {"error": "Not found"}, 404)
        else:
            send_json(self, {"error": "Method not allowed"}, 405)

# ============================================================================
# MAIN SERVER
# ============================================================================
def main():
    """Start the dashboard server"""
    print("=" * 60)
    print("Council Observability Dashboard")
    print("=" * 60)
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

    # Ensure database exists
    if not DATABASE_PATH.exists():
        print("[WARN] Database not found. Please run Initialize-DashboardDatabase.ps1")
        return

    # Ensure log directory exists (per Council: Gateway Logs)
    if GATEWAY_LOGS_AVAILABLE:
        ensure_log_directory()

    # Create server
    with socketserver.TCPServer((HOST, PORT), DashboardHandler) as httpd:
        httpd.allow_reuse_address = True

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] Server stopped")
            if SSE_AVAILABLE:
                get_sse_manager().shutdown()

if __name__ == "__main__":
    main()
