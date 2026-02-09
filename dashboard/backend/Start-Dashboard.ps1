# Start-Dashboard.ps1
# Council Observability Dashboard - HTTP Server
# Per Council decree ARCH-2024-008

<#
.SYNOPSIS
    Start the Council Observability Dashboard HTTP server

.DESCRIPTION
    Runs a PowerShell HttpListener on localhost:8080 serving:
    - Static frontend assets (index.html)
    - REST API endpoints (/api/metrics, /api/health, /api/export)
    - Real-time data for Chart.js visualizations

.EXAMPLE
    .\Start-Dashboard.ps1
    Starts dashboard on default port 8080

.EXAMPLE
    .\Start-Dashboard.ps1 -Port 8090
    Starts dashboard on port 8090
#>

[CmdletBinding()]
param(
    [int]$Port = 8080,
    [string]$DatabasePath = "$PSScriptRoot\..\data\dashboard.db",
    [switch]$Daemon
)

# ============================================================================
# CONFIGURATION
# ============================================================================
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Paths
$FrontendPath = Join-Path $PSScriptRoot "..\frontend"
$LibPath = Join-Path $PSScriptRoot "lib"
$ApiPath = Join-Path $PSScriptRoot "api"

# Security: Generate auth token if not exists
$TokenPath = Join-Path $PSScriptRoot "..\data\.auth-token"
if (-not (Test-Path $TokenPath)) {
    $token = [Guid]::NewGuid().ToString()
    $token | Out-File -FilePath $TokenPath -Encoding UTF8
    Write-Host "[SECURITY] Generated new auth token: $token" -ForegroundColor Yellow
    Write-Host "[SECURITY] Token saved to: $TokenPath" -ForegroundColor Gray
}
$AuthToken = (Get-Content $TokenPath -Raw).Trim()

# Rate limiting (per Council decree: 10 req/10s)
$script:RequestTracker = @{}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "INFO" { "White" }
        "WARN" { "Yellow" }
        "ERROR" { "Red" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-RateLimit {
    param([string]$ClientIP)

    $now = [DateTime]::UtcNow
    $windowStart = $now.AddSeconds(-10)

    # Clean old entries - collect keys to remove first to avoid enumeration error
    $keysToRemove = @($script:RequestTracker.Keys | Where-Object {
        $script:RequestTracker[$_] -lt $windowStart
    })
    foreach ($key in $keysToRemove) {
        $script:RequestTracker.Remove($key)
    }

    # Count requests from this IP
    $count = ($script:RequestTracker.Keys | Where-Object {
        $script:RequestTracker[$_] -ge $windowStart -and $_ -like "$ClientIP*"
    }).Count

    if ($count -ge 10) {
        return $false
    }

    # Track this request
    $key = "$ClientIP-$($now.Ticks)"
    $script:RequestTracker[$key] = $now
    return $true
}

function Test-AuthToken {
    param([System.Net.HttpListenerRequest]$Request)

    # Check query string
    $queryToken = $Request.QueryString["token"]
    if ($queryToken -eq $AuthToken) {
        return $true
    }

    # Check Authorization header
    $authHeader = $Request.Headers["Authorization"]
    if ($authHeader -match "^Bearer\s+(.+)$") {
        if ($Matches[1] -eq $AuthToken) {
            return $true
        }
    }

    return $false
}

function Send-JsonResponse {
    param(
        [System.Net.HttpListenerResponse]$Response,
        [object]$Data,
        [int]$StatusCode = 200
    )

    $Response.StatusCode = $StatusCode
    $Response.ContentType = "application/json"
    $Response.Headers.Add("Access-Control-Allow-Origin", "*")
    $Response.Headers.Add("Cache-Control", "no-cache, no-store")

    $json = $Data | ConvertTo-Json -Depth 10 -Compress
    $buffer = [System.Text.Encoding]::UTF8.GetBytes($json)
    $Response.ContentLength64 = $buffer.Length
    $Response.OutputStream.Write($buffer, 0, $buffer.Length)
}

function Send-FileResponse {
    param(
        [System.Net.HttpListenerResponse]$Response,
        [string]$FilePath
    )

    if (-not (Test-Path $FilePath)) {
        Send-JsonResponse -Response $Response -Data @{ error = "Not found" } -StatusCode 404
        return
    }

    $ext = [System.IO.Path]::GetExtension($FilePath)
    $contentType = switch ($ext) {
        ".html" { "text/html; charset=utf-8" }
        ".css" { "text/css; charset=utf-8" }
        ".js" { "application/javascript; charset=utf-8" }
        ".json" { "application/json; charset=utf-8" }
        ".png" { "image/png" }
        ".svg" { "image/svg+xml" }
        default { "application/octet-stream" }
    }

    $Response.ContentType = $contentType
    $Response.Headers.Add("Access-Control-Allow-Origin", "*")

    # Cache static assets for 1 hour
    if ($ext -in @(".css", ".js", ".png", ".svg")) {
        $Response.Headers.Add("Cache-Control", "max-age=3600")
    }

    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $Response.ContentLength64 = $bytes.Length
    $Response.OutputStream.Write($bytes, 0, $bytes.Length)
}

function Get-ValidatedTimeRange {
    param([string]$Range)

    $allowlist = @{
        "1h"  = 3600
        "24h" = 86400
        "7d"  = 604800
        "30d" = 2592000
    }

    if ($allowlist.ContainsKey($Range)) {
        return $allowlist[$Range]
    }

    # Safe default (per Council decree)
    return $allowlist["24h"]
}

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

function Invoke-SqlQuery {
    param(
        [string]$Query,
        [hashtable]$Parameters = @{}
    )

    try {
        # Use Python for SQLite operations (more reliable on Windows)
        $paramsJson = $Parameters | ConvertTo-Json -Compress
        $pythonCode = @"
import sqlite3
import json
import sys

try:
    conn = sqlite3.connect(r'$DatabasePath', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = '''$Query'''
    params = json.loads('''$paramsJson''')

    # Replace @param with ? for Python sqlite3
    query = query.replace('@', '?')

    cursor.execute(query, list(params.values()))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    result = [dict(zip(columns, row)) for row in rows]
    print(json.dumps(result))
    conn.close()
except Exception as e:
    print(json.dumps({"error": str(e)}), file=sys.stderr)
    sys.exit(1)
"@

        $result = python -c $pythonCode 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "SQL Error: $result" -Level ERROR
            return @(@{ error = $result })
        }

        return $result | ConvertFrom-Json
    }
    catch {
        Write-Log "Database error: $($_.Exception.Message)" -Level ERROR
        return @(@{ error = $_.Exception.Message })
    }
}

# ============================================================================
# API ENDPOINTS
# ============================================================================

function Get-MetricsEndpoint {
    param(
        [System.Net.HttpListenerRequest]$Request,
        [System.Net.HttpListenerResponse]$Response
    )

    $range = $Request.QueryString["range"]
    $after = $Request.QueryString["after"]

    $seconds = Get-ValidatedTimeRange -Range $range
    $timeFilter = "datetime(timestamp, '-$seconds seconds')"

    $whereClause = "WHERE datetime(timestamp) >= $timeFilter"
    if ($after) {
        # Validate after parameter as ISO8601 timestamp
        if ($after -match "^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}") {
            $whereClause = "WHERE timestamp > '$after'"
        }
    }

    $query = @"
SELECT
    timestamp,
    model,
    task_type,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    cost_usd,
    duration_seconds,
    status
FROM api_calls
$whereClause
ORDER BY timestamp DESC
LIMIT 1000
"@

    $data = Invoke-SqlQuery -Query $query
    Send-JsonResponse -Response $Response -Data $data
}

function Get-HealthEndpoint {
    param(
        [System.Net.HttpListenerRequest]$Request,
        [System.Net.HttpListenerResponse]$Response
    )

    # Get current gateway status
    $query = @"
SELECT
    gateway_status,
    models_available,
    response_time_ms,
    timestamp as last_check
FROM gateway_health
ORDER BY timestamp DESC
LIMIT 1
"@

    $gateway = Invoke-SqlQuery -Query $query

    # Get today's summary
    $summaryQuery = @"
SELECT
    COUNT(*) as total_calls,
    SUM(total_tokens) as total_tokens,
    SUM(cost_usd) as total_cost,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as error_count
FROM api_calls
WHERE date(timestamp) = date('now')
"@

    $summary = Invoke-SqlQuery -Query $summaryQuery

    $result = @{
        gateway = if ($gateway -and $gateway.Count -gt 0) { $gateway[0] } else { $null }
        today = if ($summary -and $summary.Count -gt 0) { $summary[0] } else { $null }
        timestamp = (Get-Date).ToString("o")
    }

    Send-JsonResponse -Response $Response -Data $result
}

function Get-ExportEndpoint {
    param(
        [System.Net.HttpListenerRequest]$Request,
        [System.Net.HttpListenerResponse]$Response
    )

    $format = $Request.QueryString["format"]
    if (-not $format) { $format = "json" }
    $range = $Request.QueryString["range"]

    $seconds = Get-ValidatedTimeRange -Range $range

    $query = @"
SELECT * FROM api_calls
WHERE datetime(timestamp) >= datetime(timestamp, '-$seconds seconds')
ORDER BY timestamp DESC
"@

    $data = Invoke-SqlQuery -Query $query

    if ($format -eq "csv") {
        # Convert to CSV
        $Response.ContentType = "text/csv; charset=utf-8"
        $Response.Headers.Add("Content-Disposition", "attachment; filename=dashboard-export.csv")

        $csv = $data | ConvertTo-Csv -NoTypeInformation
        $buffer = [System.Text.Encoding]::UTF8.GetBytes($csv)
        $Response.ContentLength64 = $buffer.Length
        $Response.OutputStream.Write($buffer, 0, $buffer.Length)
    }
    else {
        Send-JsonResponse -Response $Response -Data $data
    }
}

# ============================================================================
# MAIN SERVER LOOP
# ============================================================================

function Start-DashboardServer {
    Write-Log "Starting Council Observability Dashboard..." -Level SUCCESS
    Write-Log "Port: $Port" -Level INFO
    Write-Log "Database: $DatabasePath" -Level INFO
    Write-Log "Frontend: $FrontendPath" -Level INFO
    Write-Log "Auth Token: $AuthToken" -Level INFO
    Write-Host ""

    # Check database exists
    if (-not (Test-Path $DatabasePath)) {
        Write-Log "Database not found. Running Initialize-DashboardDatabase..." -Level WARN
        & (Join-Path $LibPath "Initialize-DashboardDatabase.ps1")
    }

    # Create listener
    $listener = [System.Net.HttpListener]::new()
    $url = "http://127.0.0.1:$Port/"
    $listener.Prefixes.Add($url)

    try {
        $listener.Start()
        Write-Log "Server listening on $url" -Level SUCCESS
        Write-Host ""
        Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
        Write-Host ""

        if ($Daemon) {
            # Daemon mode: write PID file for management
            $pidFile = Join-Path $PSScriptRoot "..\data\dashboard.pid"
            $PID | Out-File -FilePath $pidFile -Encoding UTF8
            Write-Log "Running in daemon mode (PID: $PID)" -Level INFO
        }

        # Main request loop
        while ($listener.IsListening) {
            $context = $listener.GetContext()
            $request = $context.Request
            $response = $context.Response

            $clientIP = $request.RemoteEndPoint.Address.ToString()
            $path = $request.Url.LocalPath
            $method = $request.HttpMethod

            Write-Log "$method $path from $clientIP"

            # Rate limiting
            if (-not (Test-RateLimit -ClientIP $clientIP)) {
                Write-Log "Rate limit exceeded for $clientIP" -Level WARN
                Send-JsonResponse -Response $response -Data @{ error = "Rate limit exceeded" } -StatusCode 429
                $response.Close()
                continue
            }

            try {
                # API endpoints require auth
                if ($path.Length -ge 5 -and $path.Substring(0, 5) -eq "/api/") {
                    if (-not (Test-AuthToken -Request $request)) {
                        Write-Log "Unauthorized request" -Level WARN
                        Send-JsonResponse -Response $response -Data @{ error = "Unauthorized" } -StatusCode 401
                        $response.Close()
                        continue
                    }

                    switch ($path) {
                        "/api/metrics" { Get-MetricsEndpoint -Request $request -Response $response }
                        "/api/health" { Get-HealthEndpoint -Request $request -Response $response }
                        "/api/export" { Get-ExportEndpoint -Request $request -Response $response }
                        default {
                            Send-JsonResponse -Response $response -Data @{ error = "Not found" } -StatusCode 404
                        }
                    }
                }
                # Serve static files
                else {
                    # Default to index.html
                    if ($path -eq "/" -or $path -eq "") {
                        $path = "/index.html"
                    }

                    $filePath = Join-Path $FrontendPath ($path -replace "^/", "")
                    Send-FileResponse -Response $response -FilePath $filePath
                }
            }
            catch {
                Write-Log "Error handling request: $($_.Exception.Message)" -Level ERROR
                try {
                    Send-JsonResponse -Response $response -Data @{ error = "Internal server error" } -StatusCode 500
                }
                catch {
                    # Response already sent
                }
            }
            finally {
                $response.Close()
            }
        }
    }
    finally {
        $listener.Stop()
        $listener.Close()
        Write-Log "Server stopped" -Level INFO
    }
}

# Run the server
Start-DashboardServer
