#!/usr/bin/env python3
"""Create a per-cloud OOBE answer Secret without placing credentials in Git."""
import argparse
import base64
import getpass
import json
import re
import subprocess
from xml.sax.saxutils import escape


def answer(hostname, cloud, password, version):
    # Specialize runs as SYSTEM: no password-bearing auto-logon is needed.
    script = r"""
$ErrorActionPreference = 'Stop'
$image = Get-Content C:\TeamX\image.json -Raw | ConvertFrom-Json
if ($image.version -ne 'VERSION' -or $image.team -ne 'team-x') { throw 'Unexpected golden image' }
$info = @{ team = 'team-x'; cloud = 'CLOUD'; hostname = $env:COMPUTERNAME; version = $image.version }
$info | ConvertTo-Json | Set-Content C:\inetpub\wwwroot\ready.json -Encoding UTF8
$html = '<!doctype html><html><head><title>Team X Windows</title><style>body{background:#101820;color:#fff;font:24px Segoe UI;padding:70px}h1{color:#73d8ff}p{margin:24px 0}</style></head><body><h1>Team X | Windows VM</h1><p>Cloud: CLOUD</p><p>Hostname: ' + $env:COMPUTERNAME + '</p><p>Golden image: ' + $image.version + '</p><p>One operating model. Two clouds.</p></body></html>'
$html | Set-Content C:\inetpub\wwwroot\index.html -Encoding UTF8
Remove-Item C:\inetpub\wwwroot\iisstart.htm -ErrorAction SilentlyContinue
Remove-Item C:\inetpub\wwwroot\validation.json -ErrorAction SilentlyContinue
""".replace('VERSION', version).replace('CLOUD', cloud)
    encoded = base64.b64encode(script.encode('utf-16le')).decode()
    return f'''<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
  <settings pass="specialize">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><ComputerName>{hostname}</ComputerName></component>
    <component name="Microsoft-Windows-Deployment" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <RunSynchronous><RunSynchronousCommand wcm:action="add"><Order>1</Order><Path>powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}</Path></RunSynchronousCommand></RunSynchronous>
    </component>
  </settings>
  <settings pass="oobeSystem">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <OOBE><HideEULAPage>true</HideEULAPage><HideOEMRegistrationScreen>true</HideOEMRegistrationScreen><HideOnlineAccountScreens>true</HideOnlineAccountScreens><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE><ProtectYourPC>1</ProtectYourPC></OOBE>
      <UserAccounts><AdministratorPassword><Value>{escape(password)}</Value><PlainText>true</PlainText></AdministratorPassword></UserAccounts>
      <TimeZone>UTC</TimeZone>
    </component>
  </settings>
</unattend>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--cloud', choices=['azure', 'aws'], required=True)
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--version', default='v1.0.0')
    parser.add_argument('--secret-name', default='team-x-win-v100-answer')
    parser.add_argument('--namespace', default='team-x')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,14}', args.hostname):
        parser.error('hostname must start with a letter and contain at most 15 letters, digits or hyphens')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', args.version):
        parser.error('version must be vMAJOR.MINOR.PATCH')
    password = getpass.getpass(f'Unique Administrator password for {args.cloud}: ')
    if len(password) < 14 or not all((re.search(r'[A-Z]', password), re.search(r'[a-z]', password),
                                    re.search(r'[0-9]', password), re.search(r'[^A-Za-z0-9]', password))):
        parser.error('use at least 14 characters including uppercase, lowercase, digit and symbol')
    ns = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': args.namespace}}
    subprocess.run(['oc', '--context', args.context, 'apply', '-f', '-'], input=json.dumps(ns), text=True, check=True)
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': args.secret_name, 'namespace': args.namespace}, 'type': 'Opaque',
        'stringData': {'unattend.xml': answer(args.hostname, args.cloud, password, args.version)}}
    subprocess.run(['oc', '--context', args.context, 'apply', '-f', '-'],
                   input=json.dumps(secret), text=True, check=True, capture_output=True)
    print(f'Created/updated {args.secret_name} in {args.namespace} on {args.context}; no credentials written locally.')
