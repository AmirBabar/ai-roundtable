# Add-DashboardApiCall.ps1
# Log API calls to the dashboard database

<#
.SYNOPSIS
    Logs Council model API calls to the dashboard database

.DESCRIPTION
    Records API call details including model, tokens, cost, duration, and status.
    Automatically triggers budget alert checks.

.PARAMETER Model
    The model that was called

.PARAMETER TaskType
    Type of task (brainstorming, planning, team-debate, etc.)

.PARAMETER PromptTokens
    Number of tokens in the prompt

.PARAMETER CompletionTokens
    Number of tokens in the completion

.PARAMETER TotalTokens
    Total tokens used

.PARAMETER CostUsd
    Cost in USD

.PARAMETER DurationSeconds
    Duration of the API call

.PARAMETER Status
    Status of the call (success, error, timeout)

.PARAMETER ErrorMessage
    Error message if status is not success

.PARAMETER SessionId
    Optional session identifier

.PARAMETER RequestId
    Unique identifier for the request

.EXAMPLE
    Add-DashboardApiCall -Model "gemini-architect" -TaskType "planning" -TotalTokens 1500 -CostUsd 0.08 -DurationSeconds 25 -Status "success"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Model,

    [string]$TaskType,

    [int]$PromptTokens = 0,

    [int]$CompletionTokens = 0,

    [int]$TotalTokens = 0,

    [double]$CostUsd = 0.0,

    [double]$DurationSeconds = 0,

    [ValidateSet('success', 'error', 'timeout')]
    [string]$Status = 'success',

    [string]$ErrorMessage,

    [string]$SessionId,

    [guid]$RequestId = [guid]::NewGuid()
)

$DatabasePath = "$PSScriptRoot\..\..\data\dashboard.db"

function Write-ApiCallLog {
    param(
        [string]$DbPath,
        [hashtable]$Data
    )

    $sql = @"
    INSERT INTO api_calls (
        model, task_type, prompt_tokens, completion_tokens, total_tokens,
        cost_usd, duration_seconds, status, error_message, session_id, request_id
    ) VALUES (
        @model, @task_type, @prompt_tokens, @completion_tokens, @total_tokens,
        @cost_usd, @duration_seconds, @status, @error_message, @session_id, @request_id
    );
"@

    try {
        # Try using sqlite3 CLI if available
        $sqliteExe = Get-Command sqlite3 -ErrorAction SilentlyContinue

        if ($sqliteExe) {
            # Build SQL with proper escaping
            $escapedData = @{
                model = $Data.model -replace "'", "''"
                task_type = if ($Data.task_type) { $Data.task_type -replace "'", "''" } else { "NULL" }
                prompt_tokens = $Data.prompt_tokens
                completion_tokens = $Data.completion_tokens
                total_tokens = $Data.total_tokens
                cost_usd = $Data.cost_usd.ToString().Replace(',', '.')
                duration_seconds = $Data.duration_seconds.ToString().Replace(',', '.')
                status = $Data.status
                error_message = if ($Data.error_message) { "`"$($Data.error_message -replace "'", "''")`"" } else { "NULL" }
                session_id = if ($Data.session_id) { "`"$($Data.session_id -replace "'", "''")`"" } else { "NULL" }
                request_id = $Data.request_id
            }

            $sql = @"
            INSERT INTO api_calls (model, task_type, prompt_tokens, completion_tokens, total_tokens, cost_usd, duration_seconds, status, error_message, session_id, request_id)
            VALUES ('$($escapedData.model)', $($escapedData.task_type), $($escapedData.prompt_tokens), $($escapedData.completion_tokens), $($escapedData.total_tokens), $($escapedData.cost_usd), $($escapedData.duration_seconds), '$($escapedData.status)', $($escapedData.error_message), $($escapedData.session_id), '$($escapedData.request_id)');
"@

            & sqlite3 $DbPath $sql 2>&1 | Out-Null
        }
        else {
            # Fallback: Append to CSV
            $csvPath = $DbPath -replace '\.db$', '_api_calls.csv'
            $csvLine = "$($Data.timestamp),$($Data.model),$($Data.task_type),$($Data.prompt_tokens),$($Data.completion_tokens),$($Data.total_tokens),$($Data.cost_usd),$($Data.duration_seconds),$($Data.status),`"$($Data.error_message)`",$($Data.session_id),$($Data.request_id)"
            Add-Content -Path $csvPath -Value $csvLine
        }
    }
    catch {
        # Silently fail for logging issues
    }
}

try {
    $logData = @{
        timestamp = (Get-Date).ToString("o")
        model = $Model
        task_type = $TaskType
        prompt_tokens = $PromptTokens
        completion_tokens = $CompletionTokens
        total_tokens = $TotalTokens
        cost_usd = $CostUsd
        duration_seconds = $DurationSeconds
        status = $Status
        error_message = $ErrorMessage
        session_id = $SessionId
        request_id = $RequestId
    }

    Write-ApiCallLog -DbPath $DatabasePath -Data $logData

    # Check budget thresholds
    & "$PSScriptRoot\Test-BudgetThreshold.ps1" -DatabasePath $DatabasePath -ErrorAction SilentlyContinue
}
catch {
    # Silently fail for logging issues
}
