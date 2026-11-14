$ProgressPreference = 'SilentlyContinue'
$task = Get-ScheduledTask -TaskName 'WeakCoverageCameraMTeacher'
$info = Get-ScheduledTaskInfo -TaskName 'WeakCoverageCameraMTeacher'
[ordered]@{TaskName=$task.TaskName; State=[string]$task.State; LastRunTime=$info.LastRunTime.ToString('o'); LastTaskResult=$info.LastTaskResult; UserId=$task.Principal.UserId; LogonType=[string]$task.Principal.LogonType; Action=$task.Actions.Arguments; ExecutionTimeLimit=$task.Settings.ExecutionTimeLimit; RestartCount=$task.Settings.RestartCount} | ConvertTo-Json
