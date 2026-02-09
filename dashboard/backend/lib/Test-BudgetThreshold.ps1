# Test-BudgetThreshold.ps1
# Check if budget thresholds are exceeded and create alerts

<#
.SYNOPSIS
    Checks if spending has exceeded configured budget thresholds

.DESCRIPTION
    Queries the dashboard database for today's/week's/month's spending
    and creates alerts if thresholds are exceeded.

.PARAMETER DatabasePath
    Path to the dashboard database
#>

[CmdletBinding()]
param(
    [string]$DatabasePath = "$PSScriptRoot\..\..\data\dashboard.db"
)

try {
    $sqliteExe = Get-Command sqlite3 -ErrorAction SilentlyContinue

    if (-not $sqliteExe) {
        return
    }

    # Get budget thresholds from settings
    $settings = & sqlite3 $DatabasePath "SELECT key, value FROM settings;" 2>$null |
        ConvertFrom-Csv -Delimiter '|' -Header "Key","Value"

    $dailyBudget = [double]($settings | Where-Object { $_.Key -eq "daily_budget_usd" }).Value
    $weeklyBudget = [double]($settings | Where-Object { $_.Key -eq "weekly_budget_usd" }).Value
    $monthlyBudget = [double]($settings | Where-Object { $_.Key -eq "monthly_budget_usd" }).Value

    # Check today's spending
    $todayCost = & sqlite3 $DatabasePath "SELECT COALESCE(SUM(cost_usd), 0) FROM api_calls WHERE date(timestamp) = date('now');" 2>$null

    if ([double]$todayCost -gt $dailyBudget) {
        Write-Host "[WARN]️ DAILY BUDGET ALERT: Spent `$$todayCost (budget: `$$dailyBudget)" -ForegroundColor Yellow
        # Create alert in database
        & sqlite3 $DatabasePath "INSERT INTO budget_alerts (alert_type, threshold_usd, actual_usd) VALUES ('daily', $dailyBudget, $todayCost);" 2>&1 | Out-Null
    }

    # Check this week's spending
    $weekCost = & sqlite3 $DatabasePath "SELECT COALESCE(SUM(cost_usd), 0) FROM api_calls WHERE date(timestamp) >= date('now', '-7 days');" 2>$null

    if ([double]$weekCost -gt $weeklyBudget) {
        Write-Host "[WARN]️ WEEKLY BUDGET ALERT: Spent `$$weekCost (budget: `$$weeklyBudget)" -ForegroundColor Yellow
        & sqlite3 $DatabasePath "INSERT INTO budget_alerts (alert_type, threshold_usd, actual_usd) VALUES ('weekly', $weeklyBudget, $weekCost);" 2>&1 | Out-Null
    }

    # Check this month's spending
    $monthCost = & sqlite3 $DatabasePath "SELECT COALESCE(SUM(cost_usd), 0) FROM api_calls WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now');" 2>$null

    if ([double]$monthCost -gt $monthlyBudget) {
        Write-Host "[WARN]️ MONTHLY BUDGET ALERT: Spent `$$monthCost (budget: `$$monthlyBudget)" -ForegroundColor Yellow
        & sqlite3 $DatabasePath "INSERT INTO budget_alerts (alert_type, threshold_usd, actual_usd) VALUES ('monthly', $monthlyBudget, $monthCost);" 2>&1 | Out-Null
    }
}
catch {
    # Silently fail
}
