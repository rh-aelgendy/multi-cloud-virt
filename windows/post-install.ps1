$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$mutex = New-Object System.Threading.Mutex($false, 'Global\TeamXGoldenImageBuild')
if (-not $mutex.WaitOne(0)) { exit 0 }
New-Item -ItemType Directory -Path C:\TeamX -Force | Out-Null
Start-Transcript -Path C:\TeamX\build.log -Force
try {
    Copy-Item $PSCommandPath C:\TeamX\finish-image.ps1 -Force -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\TeamX\finish-image.ps1'
    Register-ScheduledTask -TaskName TeamXImageBuild -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -User SYSTEM -RunLevel Highest -Force | Out-Null
    $reboot = $false
    if (-not (Test-Path C:\TeamX\drivers-installed)) {
        foreach ($msi in @('E:\virtio-win-gt-x64.msi', 'E:\guest-agent\qemu-ga-x86_64.msi')) {
            $p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList "/i $msi /qn /norestart"
            if ($p.ExitCode -notin @(0, 3010)) { throw "MSI failed: $msi ($($p.ExitCode))" }
            if ($p.ExitCode -eq 3010) { $reboot = $true }
        }
        New-Item C:\TeamX\drivers-installed -ItemType File -Force | Out-Null
    }
    if (-not (Test-Path C:\TeamX\iis-installed)) {
        $feature = Install-WindowsFeature Web-Server -IncludeManagementTools
        if (-not $feature.Success) { throw 'IIS install failed' }
        if ($feature.RestartNeeded -eq 'Yes') { $reboot = $true }
        New-Item C:\TeamX\iis-installed -ItemType File -Force | Out-Null
    }
    if ($reboot) {
        Stop-Transcript
        Restart-Computer -Force
        while ($true) { Start-Sleep -Seconds 60 }
    }
    Set-Service W3SVC -StartupType Automatic
    Start-Service W3SVC
    Start-Service QEMU-GA
    if (-not (Get-NetFirewallRule -DisplayName 'Team X demo HTTP' -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName 'Team X demo HTTP' -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow | Out-Null
    }
    $image = @{ team = 'team-x'; version = '@IMAGE_VERSION@'; builtAt = (Get-Date).ToUniversalTime().ToString('o') }
    $image | ConvertTo-Json | Set-Content C:\TeamX\image.json -Encoding UTF8
    if ((Get-Service QEMU-GA).Status -ne 'Running') { throw 'Guest agent is not running' }
    if ((Get-Service W3SVC).Status -ne 'Running') { throw 'IIS is not running' }
    'Team X golden image validation' | Set-Content C:\inetpub\wwwroot\index.html
    if ((Invoke-WebRequest http://localhost/index.html -UseBasicParsing).StatusCode -ne 200) { throw 'IIS HTTP test failed' }
    @{ passed = $true; team = 'team-x'; version = '@IMAGE_VERSION@'; checks = @('virtio-msi', 'guest-agent', 'iis-service', 'http-200') } |
        ConvertTo-Json | Set-Content C:\inetpub\wwwroot\validation.json -Encoding UTF8
    # Give the controller time to capture validation evidence before shutdown.
    Start-Sleep -Seconds 180
    Unregister-ScheduledTask -TaskName TeamXImageBuild -Confirm:$false
    Remove-Item C:\TeamX\finish-image.ps1 -ErrorAction SilentlyContinue
    Remove-Item C:\Windows\Panther\unattend.xml -ErrorAction SilentlyContinue
    Remove-Item C:\Windows\Panther\Unattend\unattend.xml -ErrorAction SilentlyContinue
    (New-Object -ComObject Shell.Application).NameSpace(17).ParseName('F:').InvokeVerb('Eject')
    Start-Sleep -Seconds 5
    if (Test-Path F:\autounattend.xml) { throw 'Answer media did not eject; refusing to seal' }
    Stop-Transcript
    $p = Start-Process C:\Windows\System32\Sysprep\Sysprep.exe -ArgumentList '/generalize /oobe /shutdown /mode:vm' -PassThru -Wait
    if ($p.ExitCode -ne 0) { throw "Sysprep failed: $($p.ExitCode)" }
    while ($true) { Start-Sleep -Seconds 60 }
} catch {
    $_ | Out-String | Set-Content C:\TeamX\FAILED.txt
    Remove-Item C:\inetpub\wwwroot\validation.json -ErrorAction SilentlyContinue
    Write-Error $_ -ErrorAction Continue
    # Keep powered on for inspection; failure must not look like successful shutdown.
    while ($true) { Start-Sleep -Seconds 60 }
}
