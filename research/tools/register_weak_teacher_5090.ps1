$ErrorActionPreference = 'Stop'
$taskName = 'WeakCoverageCameraMTeacher'
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Refusing to overwrite existing task' }
$action = New-ScheduledTaskAction -Execute 'C:\Windows\System32\wsl.exe' -Argument '-d Ubuntu-22.04 -u root -e bash /root/wzl/weak_coverage_camera_m_teacher/tools/start_weak_teacher_5090_foreground.sh'
$principal = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType S4U -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -Hidden
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Description 'One-off frozen camera YOLOX-M teacher training; fresh COCO, no test, no retry' | Select-Object TaskName,State
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime,LastTaskResult
