$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wsl.exe -d Ubuntu-22.04 -u root -e bash /mnt/c/Users/Administrator/workstation_persistent_resume.sh'}
$result | Select-Object ProcessId,ReturnValue
