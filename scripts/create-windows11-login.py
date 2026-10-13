#!/usr/bin/env python3
"""Create a unique Windows 11 demo login in a cluster Secret; preserve existing credentials."""
import argparse
import getpass
import json
import re
import secrets
import subprocess
from xml.sax.saxutils import escape


def answer(hostname, username, password):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
  <settings pass="specialize">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><ComputerName>{escape(hostname)}</ComputerName></component>
  </settings>
  <settings pass="oobeSystem">
    <component name="Microsoft-Windows-International-Core" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <InputLocale>en-US</InputLocale><SystemLocale>en-US</SystemLocale><UILanguage>en-US</UILanguage><UserLocale>en-US</UserLocale>
    </component>
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <OOBE><HideEULAPage>true</HideEULAPage><HideOEMRegistrationScreen>true</HideOEMRegistrationScreen><HideOnlineAccountScreens>true</HideOnlineAccountScreens><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE><ProtectYourPC>3</ProtectYourPC></OOBE>
      <UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Name>{escape(username)}</Name><DisplayName>Team X Developer</DisplayName><Group>Administrators</Group><Password><Value>{escape(password)}</Value><PlainText>true</PlainText></Password></LocalAccount></LocalAccounts></UserAccounts>
      <TimeZone>UTC</TimeZone>
      <FirstLogonCommands><SynchronousCommand wcm:action="add"><Order>1</Order><CommandLine>powershell.exe -NoProfile -Command "Set-LocalUser -Name '{escape(username)}' -PasswordNeverExpires $true"</CommandLine><Description>Keep the demo login ready for later rehearsal</Description></SynchronousCommand></FirstLogonCommands>
    </component>
  </settings>
</unattend>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True)
    parser.add_argument('--namespace',default='windows-vms-vdi')
    parser.add_argument('--secret-name',default='win11-dev-01-answer')
    parser.add_argument('--hostname',default='WIN11-DEV-01')
    parser.add_argument('--username',default='demo')
    parser.add_argument('--generate',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,14}',args.hostname):parser.error('Use a Windows hostname of at most 15 letters, digits or hyphens')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,19}',args.username):parser.error('Use a simple Windows local username')
    cmd=['oc','--context',args.context,'-n',args.namespace]
    exists=subprocess.run(cmd+['get','secret',args.secret_name,'--ignore-not-found','-o','name'],text=True,capture_output=True,check=True)
    if exists.stdout.strip():
        print('Preserved existing login Secret '+args.secret_name)
        return
    password=secrets.token_urlsafe(24)+'Aa1!' if args.generate else getpass.getpass('Unique Windows 11 demo password: ')
    if len(password)<14 or not all(re.search(pattern,password) for pattern in [r'[A-Z]',r'[a-z]',r'[0-9]',r'[^A-Za-z0-9]']):parser.error('Use at least 14 characters with uppercase, lowercase, digit and symbol')
    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':args.secret_name,'namespace':args.namespace,'labels':{'demo':'windows11-developer'}},'stringData':{'username':args.username,'password':password,'unattend.xml':answer(args.hostname,args.username,password)}}
    subprocess.run(cmd+['create','-f','-'],input=json.dumps(obj),text=True,capture_output=True,check=True)
    print('Created '+args.namespace+'/'+args.secret_name+'; username '+args.username+'; reveal key password only in the cluster Console')


if __name__=='__main__':main()
