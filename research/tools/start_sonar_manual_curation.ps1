param(
    [int]$Port = 8765,
    [string]$OutputDirectory = '',
    [switch]$TestMode
)
$ErrorActionPreference = 'Stop'
$curationRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$curationScript = Join-Path $PSScriptRoot 'sonar_manual_curation_server.py'
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $curationRoot 'DataSet/sonar_manual_curation'
}
$curationOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
$curationProduction = [System.IO.Path]::GetFullPath((Join-Path $curationRoot 'DataSet/sonar_manual_curation'))
if ($TestMode -and $curationOutput -eq $curationProduction) { throw 'Test mode requires a separate output directory.' }
New-Item -ItemType Directory -Path $curationOutput -Force | Out-Null
$curationInfoPath = Join-Path $curationOutput 'server-info.json'
if (Test-Path -LiteralPath $curationInfoPath) {
    $curationExisting = Get-Content -LiteralPath $curationInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $curationExistingProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($curationExisting.pid)"
    if ($curationExistingProcess -and $curationExistingProcess.CommandLine -like '*sonar_manual_curation_server.py*' -and $curationExistingProcess.CommandLine.Contains($curationOutput)) {
        Write-Output "Already running: $($curationExisting.url), PID $($curationExisting.pid)"
        return
    }
}
$curationPython = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe'
if (-not (Test-Path -LiteralPath $curationPython)) { $curationPython = (Get-Command python -ErrorAction Stop).Source }
$curationTimestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$curationStdout = Join-Path $curationOutput "server-$curationTimestamp.stdout.log"
$curationStderr = Join-Path $curationOutput "server-$curationTimestamp.stderr.log"
$curationArgs = @('-u', '-B', '-X', 'utf8', ('"' + $curationScript + '"'), '--port', $Port, '--out', ('"' + $curationOutput + '"'))
if ($TestMode) { $curationArgs += '--test-mode' }
$curationProcess = Start-Process -FilePath $curationPython -ArgumentList $curationArgs -WorkingDirectory $curationRoot -WindowStyle Hidden -RedirectStandardOutput $curationStdout -RedirectStandardError $curationStderr -PassThru
for ($curationAttempt = 0; $curationAttempt -lt 150; $curationAttempt++) {
    $curationProcess.Refresh()
    if ($curationProcess.HasExited) {
        $curationFailure = Get-Content -LiteralPath $curationStderr -Raw -Encoding UTF8
        throw "Curation server exited. Details: $curationFailure"
    }
    if (Test-Path -LiteralPath $curationInfoPath) {
        try {
            $curationInfo = Get-Content -LiteralPath $curationInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($curationInfo.pid -eq $curationProcess.Id) {
                Write-Output "Ready: $($curationInfo.url), PID $($curationInfo.pid)"
                Write-Output "Review data: $curationOutput"
                Write-Output "Log: $curationStdout"
                return
            }
        } catch { }
    }
    Start-Sleep -Milliseconds 300
}
Write-Output "Starting in background, PID $($curationProcess.Id). Read $curationInfoPath or $curationStderr for status."
