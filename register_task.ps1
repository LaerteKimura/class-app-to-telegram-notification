# Run this script as Administrator once to register the scheduled task.
# In Claude Code: ! powershell -ExecutionPolicy Bypass -File "C:\PYTHON_PROJECTS\ClassApp\register_task.ps1"

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Checks ClassApp for new school messages and sends them to Telegram</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Repetition>
        <Interval>PT12H</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$env:USERDOMAIN\$env:USERNAME</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\PYTHON_PROJECTS\ClassApp\app\.venv\Scripts\python.exe</Command>
      <Arguments>"C:\PYTHON_PROJECTS\ClassApp\app\main.py" run</Arguments>
      <WorkingDirectory>C:\PYTHON_PROJECTS\ClassApp\app</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = "$env:TEMP\classapp_task.xml"
$xml | Out-File -FilePath $xmlPath -Encoding Unicode

schtasks /create /tn "ClassApp Notifier" /xml $xmlPath /f

if ($LASTEXITCODE -eq 0) {
    Write-Host "Task registered successfully." -ForegroundColor Green
    Write-Host "It will run at every logon and repeat every 12 hours."
    Write-Host "To run it right now: schtasks /run /tn `"ClassApp Notifier`""
} else {
    Write-Host "Registration failed. Make sure you are running as Administrator." -ForegroundColor Red
}

Remove-Item $xmlPath -ErrorAction SilentlyContinue
