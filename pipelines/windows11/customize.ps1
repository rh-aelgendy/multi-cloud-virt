$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$mode = '@MODE@'
$version = '@IMAGE_VERSION@'
$mutex = New-Object System.Threading.Mutex($false, 'Global\Win11ImageFactory')
if (-not $mutex.WaitOne(0)) { exit 0 }
$root = 'C:\ImageFactory'
New-Item $root -ItemType Directory -Force | Out-Null
Start-Transcript -Path "$root\build.log" -Append
try {
    $os = (Get-CimInstance Win32_OperatingSystem).Caption
    if ($os -notmatch 'Windows 11') { throw "Expected Windows 11, got $os" }
    Copy-Item $PSCommandPath "$root\resume.ps1" -Force -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute PowerShell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\ImageFactory\resume.ps1'
    Register-ScheduledTask Win11ImageFactory -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -User SYSTEM -RunLevel Highest -Force | Out-Null
    $restart = $false
    if (-not (Test-Path "$root\tools-installed")) {
        $drive = Get-PSDrive -PSProvider FileSystem | Where-Object { Test-Path (Join-Path $_.Root 'virtio-win-gt-x64.msi') } | Select-Object -First 1
        if (-not $drive) { throw 'VirtIO driver CD is missing' }
        foreach ($relative in @('virtio-win-gt-x64.msi', 'guest-agent\qemu-ga-x86_64.msi')) {
            $msi = Join-Path $drive.Root $relative
            $p = Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /qn /norestart" -Wait -PassThru
            if ($p.ExitCode -notin @(0,3010)) { throw "Guest tools install failed: $($p.ExitCode)" }
            if ($p.ExitCode -eq 3010) { $restart = $true }
        }
        New-Item "$root\tools-installed" -ItemType File -Force | Out-Null
    }
    if ($restart) {
        Stop-Transcript
        Restart-Computer -Force
        while ($true) { Start-Sleep 60 }
    }
    Set-Service QEMU-GA -StartupType Automatic
    Start-Service QEMU-GA
    if ((Get-Service QEMU-GA).Status -ne 'Running') { throw 'QEMU guest agent is not running' }
    $checks = @('windows11','virtio-tools','guest-agent')
    if ($mode -eq 'developer') {
        $setup = "$root\VSCodeSetup.exe"
        Invoke-WebRequest -Uri '@VSCODE_URL@' -OutFile $setup -UseBasicParsing
        if ((Get-FileHash $setup -Algorithm SHA256).Hash.ToLower() -ne '@VSCODE_SHA256@') { throw 'VS Code checksum mismatch' }
        $signature = Get-AuthenticodeSignature $setup
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'VS Code signature is not valid Microsoft code' }
        $p = Start-Process $setup -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /MERGETASKS=!runcode,addcontextmenufiles,addcontextmenufolders,addtopath' -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "VS Code install failed: $($p.ExitCode)" }
        $code = "$env:ProgramFiles\Microsoft VS Code\Code.exe"
        if (-not (Test-Path $code)) { throw 'VS Code system installation not found' }
        if ((Get-Item $code).VersionInfo.ProductVersion -notlike '@VSCODE_VERSION@*') { throw 'Unexpected VS Code version' }
        $cliVersion = & "$env:ProgramFiles\Microsoft VS Code\bin\code.cmd" --version
        if ($LASTEXITCODE -ne 0 -or $cliVersion[0].Trim() -ne '@VSCODE_VERSION@') { throw 'VS Code CLI validation failed' }
        $workspace = 'C:\TeamX\workspace'
        $desktop = 'C:\Users\Public\Desktop\Team X Developer Desktop'
        New-Item $workspace,$desktop -ItemType Directory -Force | Out-Null
        @'
# Team X developer desktop

Built automatically on Azure Red Hat OpenShift using Tekton and OpenShift Virtualization.

Included: Microsoft VS Code (system installation), VirtIO drivers and QEMU guest agent.
Open hello.ps1 in VS Code, then run it in PowerShell.
This workspace is part of the versioned golden image, so every VM starts consistently.
'@ | Set-Content "$workspace\README.md" -Encoding UTF8
        & icacls.exe $workspace /grant '*S-1-5-32-545:(OI)(CI)M' /T | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Workspace permissions could not be configured' }
        'Write-Host "Hello from Team X!" -ForegroundColor Cyan; Get-CimInstance Win32_OperatingSystem | Select-Object CSName,Caption,Version,BuildNumber' | Set-Content "$workspace\hello.ps1" -Encoding UTF8
        $info = @{ team='team-x'; platform='ARO'; os=$os; imageVersion=$version; vscodeVersion='@VSCODE_VERSION@'; builtAt=(Get-Date).ToUniversalTime().ToString('o') }
        $info | ConvertTo-Json | Set-Content C:\TeamX\image.json -Encoding UTF8
        "<html><head><title>Team X Developer Desktop</title></head><body style='font:22px Segoe UI;padding:40px;background:#112233;color:white'><h1>Team X Developer Desktop</h1><p>Built on ARO using Tekton</p><p>Windows 11 + VS Code @VSCODE_VERSION@ + VirtIO/QEMU tools</p><p>Golden image: $version</p><p>Open the Team X workspace shortcut to inspect README.md and hello.ps1.</p></body></html>" | Set-Content "$desktop\Welcome.html" -Encoding UTF8
        $shell = New-Object -ComObject WScript.Shell
        $link = $shell.CreateShortcut('C:\Users\Public\Desktop\Team X - VS Code.lnk')
        $link.TargetPath = $code
        $link.Arguments = 'C:\TeamX\workspace'
        $link.WorkingDirectory = $workspace
        $link.Save()
        if (-not (Test-Path "$workspace\hello.ps1") -or -not (Test-Path 'C:\Users\Public\Desktop\Team X - VS Code.lnk')) { throw 'Desktop customization is incomplete' }
        $checks += @('vscode-system-install','vscode-cli','sample-project','desktop-shortcuts')
        Remove-Item $setup
    }
    if ((Get-BitLockerVolume -MountPoint C:).VolumeStatus -ne 'FullyDecrypted') { throw 'Golden disks must be fully decrypted before Sysprep and cloning' }
    $result = @{ passed=$true; mode=$mode; version=$version; os=$os; checks=$checks }
    if ($mode -eq 'developer') { $result.vscodeVersion='@VSCODE_VERSION@'; $result.workspace='C:\TeamX\workspace'; $result.desktopShortcut='Team X - VS Code' }
    $json = $result | ConvertTo-Json -Depth 4
    $json | Set-Content "$root\validation.json" -Encoding UTF8
    New-NetFirewallRule -DisplayName 'Temporary Image Factory Validation' -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow | Out-Null
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add('http://+:8080/')
    $listener.Start()
    # Keep validation readable while the Tekton task captures it and the guest-agent condition.
    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        $pending = $listener.BeginGetContext($null,$null)
        while (-not $pending.AsyncWaitHandle.WaitOne(1000) -and (Get-Date) -lt $deadline) {}
        if ($pending.IsCompleted) {
            $request = $listener.EndGetContext($pending)
            $bytes = [Text.Encoding]::UTF8.GetBytes($json)
            $request.Response.ContentType = 'application/json'
            $request.Response.ContentLength64 = $bytes.Length
            $request.Response.OutputStream.Write($bytes,0,$bytes.Length)
            $request.Response.Close()
        }
    }
    $listener.Stop()
    Remove-NetFirewallRule -DisplayName 'Temporary Image Factory Validation'
    Unregister-ScheduledTask Win11ImageFactory -Confirm:$false
    Remove-Item "$root\resume.ps1" -Force
    Remove-Item C:\Windows\Panther\unattend.xml,C:\Windows\Panther\Unattend\unattend.xml -Force -ErrorAction SilentlyContinue
    $answer = Get-PSDrive -PSProvider FileSystem | Where-Object { Test-Path (Join-Path $_.Root 'customize.ps1') } | Select-Object -First 1
    if ($answer) {
        (New-Object -ComObject Shell.Application).NameSpace(17).ParseName($answer.Name+':').InvokeVerb('Eject')
        Start-Sleep 5
        if (Test-Path (Join-Path $answer.Root 'customize.ps1')) { throw 'Answer CD did not eject' }
    }
    Stop-Transcript
    $p = Start-Process C:\Windows\System32\Sysprep\Sysprep.exe -ArgumentList '/generalize /oobe /shutdown /mode:vm' -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Sysprep failed: $($p.ExitCode)" }
    while ($true) { Start-Sleep 60 }
} catch {
    $_ | Out-String | Set-Content "$root\FAILED.txt"
    Write-Error $_ -ErrorAction Continue
    # Leave failed builders running for inspection; do not publish failure as shutdown success.
    while ($true) { Start-Sleep 60 }
}
