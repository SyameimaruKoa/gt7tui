<#
.SYNOPSIS
Launch gt7tui (visual TUI frontend for Gran Turismo 7 telemetry on PS4).

.DESCRIPTION
run_gt7tui.ps1 starts gt7tui in live mode (--live <PS4_IP>) or demo mode (--demo).
If no arguments are provided, or -h/--help/Help is requested, this help is shown.
The script passes supported options to: python -m gt7tui

.PARAMETER Live
PS4 IP address for live telemetry mode.

.PARAMETER Demo
Run demo mode with continuously varying mock telemetry.

.PARAMETER Bind
UDP bind address (default: 0.0.0.0).

.PARAMETER RecvPort
UDP receive port (default: 33740).

.PARAMETER SendPort
UDP heartbeat destination port (default: 33739).

.PARAMETER Timeout
UDP receive timeout in seconds (default: 10.0).

.PARAMETER RefreshHz
UI refresh rate upper bound in Hz (default: 20.0).

.PARAMETER Version
Show gt7tui version.

.EXAMPLE
./scripts/run_gt7tui.ps1 -Live 192.168.1.50

.EXAMPLE
./scripts/run_gt7tui.ps1 -Demo

.EXAMPLE
Get-Help ./scripts/run_gt7tui.ps1 -Detailed
#>

#region Parameters
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Live,

    [Parameter(Mandatory = $false)]
    [switch]$Demo,

    [Parameter(Mandatory = $false)]
    [string]$Bind,

    [Parameter(Mandatory = $false)]
    [int]$RecvPort,

    [Parameter(Mandatory = $false)]
    [int]$SendPort,

    [Parameter(Mandatory = $false)]
    [double]$Timeout,

    [Parameter(Mandatory = $false)]
    [double]$RefreshHz,

    [Parameter(Mandatory = $false)]
    [switch]$Version,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)
#endregion

#region Help
function Show-Help {
    $helpText = @'
run_gt7tui.ps1 - Launch gt7tui (visual TUI frontend for Gran Turismo 7 telemetry on PS4)

USAGE:
    .\scripts\run_gt7tui.ps1 -Live <PS4_IP> [options]
    .\scripts\run_gt7tui.ps1 -Demo [options]
    .\scripts\run_gt7tui.ps1 -h|--help
    Get-Help .\scripts\run_gt7tui.ps1 -Detailed

MODES (exclusive):
    -Live <PS4_IP>    Connect to PS4 GT7 telemetry at the specified IP address
    -Demo             Run demo mode with continuously varying mock telemetry

OPTIONS:
    -Bind <addr>        UDP bind address (default: 0.0.0.0)
    -RecvPort <port>    UDP receive port (default: 33740)
    -SendPort <port>    UDP heartbeat destination port (default: 33739)
    -Timeout <sec>      UDP receive timeout seconds (default: 10.0)
    -RefreshHz <hz>     UI refresh rate upper bound (default: 20.0)
    -Version            Show gt7tui version

NOTES:
    - Run inside a Python virtual environment with dependencies installed.
    - PS4 and this device must be on the same reachable network (UDP 33739/33740).
    - Optional config: .\gt7tui.json (fixed path). Priority: defaults < file < CLI.
    - In-app keys: q quit, r reconnect (live), 1/2/3 tabs, ? help.
'@
    Write-Host $helpText
}
#endregion

#region Main
$allArgs = @()
if ($RemainingArgs) { $allArgs += $RemainingArgs }
foreach ($a in $args) { $allArgs += $a }

if (($PSBoundParameters.Count -eq 0 -and $allArgs.Count -eq 0)) {
    Show-Help
    exit 0
}

foreach ($a in $allArgs) {
    if ($a -eq '-h' -or $a -eq '--help' -or $a -eq '/?' -or $a -eq '-Help') {
        Show-Help
        exit 0
    }
}

if ($PSBoundParameters.ContainsKey('Live') -and $Demo) {
    Write-Host 'Error: -Live and -Demo are exclusive.' -ForegroundColor Red
    Show-Help
    exit 2
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
$venvPy = Join-Path $rootDir '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    $python = $venvPy
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = 'python'
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $python = 'python3'
} else {
    Write-Host 'Error: Python not found.' -ForegroundColor Red
    exit 1
}

$cmdArgs = @()
if ($Version) { $cmdArgs += '--version' }
if ($Demo) { $cmdArgs += '--demo' }
if ($PSBoundParameters.ContainsKey('Live') -and $Live) { $cmdArgs += @('--live', $Live) }
if ($PSBoundParameters.ContainsKey('Bind') -and $Bind) { $cmdArgs += @('--bind', $Bind) }
if ($PSBoundParameters.ContainsKey('RecvPort')) { $cmdArgs += @('--recv-port', "$RecvPort") }
if ($PSBoundParameters.ContainsKey('SendPort')) { $cmdArgs += @('--send-port', "$SendPort") }
if ($PSBoundParameters.ContainsKey('Timeout')) { $cmdArgs += @('--timeout', "$Timeout") }
if ($PSBoundParameters.ContainsKey('RefreshHz')) { $cmdArgs += @('--refresh-hz', "$RefreshHz") }
if ($allArgs.Count -gt 0) { $cmdArgs += $allArgs }

Set-Location $rootDir
& $python -m gt7tui @cmdArgs
exit $LASTEXITCODE
#endregion
