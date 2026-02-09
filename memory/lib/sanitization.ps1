# sanitization.ps1
# Council Memory - Sanitization Layer
# PII and credential filtering before storage

<#
.SYNOPSIS
    Sanitize input text by removing sensitive information

.DESCRIPTION
    Applies regex patterns to remove PII, credentials, and paths
    Returns sanitized text with redaction report
#>
function Invoke-SanitizationInput {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
        [string]$TextInput,

        [string]$DatabasePath = "$PSScriptRoot\..\data\council_memory.db"
    )

    if (-not $TextInput) {
        return $TextInput
    }

    # Load active rules from database
    $rules = Get-SanitizationRules -DatabasePath $DatabasePath

    $sanitized = $TextInput
    $redactions = @()

    foreach ($rule in $rules) {
        $pattern = $rule.pattern
        $replacement = $rule.replacement
        $ruleName = $rule.rule_name

        try {
            # Find all matches
            $matches = [regex]::Matches($TextInput, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)

            foreach ($match in $matches) {
                $matchedText = $match.Value
                $sanitized = $sanitized -replace [regex]::Escape($matchedText), $replacement

                $redactions += @{
                    rule = $ruleName
                    matched = $matchedText
                    position = $match.Index
                }
            }
        }
        catch {
            Write-Warning "Invalid regex in rule '$ruleName': $pattern"
        }
    }

    # Additional system prompt injection blocking
    $blockedPatterns = @(
        'Ignore previous instructions',
        'Ignore all instructions',
        'Disregard',
        'SYSTEM:',
        '<jailbreak>',
        '<injection>'
    )

    foreach ($blocked in $blockedPatterns) {
        if ($TextInput.IndexOf($blocked) -ge 0) {
            $sanitized = $sanitized -replace [regex]::Escape($blocked), '[BLOCKED_CMD]'
            $redactions += @{
                rule = 'prompt_injection'
                matched = $blocked
                position = $TextInput.IndexOf($blocked)
            }
        }
    }

    if ($redactions.Count -gt 0) {
        Write-Verbose "Sanitized $($redactions.Count) items: $($redactions.rule -join ', ')"
    }

    return $sanitized
}

<#
.SYNOPSIS
    Sanitize a hashtable (for metadata)

.DESCRIPTION
    Applies sanitization to all string values in a hashtable
#>
function Invoke-SanitizationHashtable {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [hashtable]$Input,

        [string]$DatabasePath = "$PSScriptRoot\..\data\council_memory.db"
    )

    $result = @{}

    foreach ($key in $Input.Keys) {
        $value = $Input[$key]

        if ($value -is [string]) {
            $result[$key] = Invoke-SanitizationInput -TextInput $value -DatabasePath $DatabasePath
        }
        elseif ($value -is [hashtable]) {
            $result[$key] = Invoke-SanitizationHashtable -Input $value -DatabasePath $DatabasePath
        }
        elseif ($value -is [array]) {
            $result[$key] = ($value | ForEach-Object {
                if ($_ -is [string]) {
                    Invoke-SanitizationInput -Input $_ -DatabasePath $DatabasePath
                } else {
                    $_
                }
            })
        }
        else {
            $result[$key] = $value
        }
    }

    return $result
}

<#
.SYNOPSIS
    Load active sanitization rules from database

.DESCRIPTION
    Returns list of active sanitization rules
#>
function Get-SanitizationRules {
    [CmdletBinding()]
    param(
        [string]$DatabasePath = "$PSScriptRoot\..\data\council_memory.db"
    )

    if (-not (Test-Path $DatabasePath)) {
        Write-Warning "Database not found: $DatabasePath"
        return @()
    }

    # Import db_adapter functions
    $dbAdapterPath = "$PSScriptRoot\db_adapter.ps1"
    if (Test-Path $dbAdapterPath) {
        . $dbAdapterPath
    } else {
        Write-Warning "db_adapter.ps1 not found"
        return @()
    }

    $query = "SELECT rule_name, pattern, replacement FROM sanitization_rules WHERE is_active = 1;"

    $result = Invoke-CouncilQuery -Query $query -DatabasePath $DatabasePath

    if ($result) {
        # Parse pipe-delimited output from SQLite
        # Only split on the first two pipes (field separators)
        $lines = $result -split "`n"
        $rules = @()
        foreach ($line in $lines) {
            if ($line -match '^([^|]+)\|(.+)\|(.+)$') {
                $rules += @{
                    rule_name = $matches[1]
                    pattern = $matches[2]
                    replacement = $matches[3]
                }
            }
        }
        return $rules
    }

    return @()
}

<#
.SYNOPSIS
    Add a custom sanitization rule

.DESCRIPTION
    Adds a new regex pattern to the sanitization rules
#>
function Add-SanitizationRule {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$RuleName,

        [Parameter(Mandatory=$true)]
        [string]$Pattern,

        [string]$Replacement = '[REDACTED]',

        [ValidateSet('pii', 'credential', 'path', 'internal', 'custom')]
        [string]$Category = 'custom',

        [string]$DatabasePath = "$PSScriptRoot\..\data\council_memory.db"
    )

    # Validate regex
    try {
        $null = [regex]::Match("", $Pattern)
    }
    catch {
        Write-Error "Invalid regex pattern: $($_.Exception.Message)"
        return $false
    }

    $escapedRuleName = $RuleName -replace "'", "''"
    $escapedPattern = $Pattern -replace "'", "''"
    $escapedReplacement = $Replacement -replace "'", "''"

    $query = @"
INSERT OR REPLACE INTO sanitization_rules (rule_name, pattern, replacement, category)
VALUES ('$escapedRuleName', '$escapedPattern', '$escapedReplacement', '$Category');
"@

    $result = Invoke-CouncilQuery -Query $query -DatabasePath $DatabasePath

    return ($LASTEXITCODE -eq 0)
}

# Export functions - only when loaded as module, not when dot-sourced
if ($MyInvocation.InvocationName -ne '.') {
    Export-ModuleMember -Function Invoke-SanitizationInput, Invoke-SanitizationHashtable, Get-SanitizationRules, Add-SanitizationRule
}
