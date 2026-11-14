param([Parameter(Mandatory = $true)][int]$ProcessId)
$ErrorActionPreference = 'Stop'
$curationProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
if (-not $curationProcess) { Write-Output "PID $ProcessId is already stopped."; return }
if ($curationProcess.CommandLine -notlike '*sonar_manual_curation_server.py*') {
    throw "PID $ProcessId is not the curation server. No process was stopped."
}
Stop-Process -Id $ProcessId
Write-Output "Stopped curation server PID $ProcessId. Saved reviews are preserved."
