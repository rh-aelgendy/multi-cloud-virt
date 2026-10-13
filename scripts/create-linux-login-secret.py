#!/usr/bin/env python3
"""Create a Linux console-login Secret for KubeVirt guest-agent propagation."""
import argparse
import getpass
import json
import secrets
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context', required=True)
parser.add_argument('--namespace', default='team-x')
parser.add_argument('--username', default='fedora')
parser.add_argument('--secret-name', default='linux-vm-login')
parser.add_argument('--generate', action='store_true', help='Generate a unique password instead of prompting')
args = parser.parse_args()
base = ['oc', '--context', args.context, '-n', args.namespace]
existing = subprocess.run(base + ['get', 'secret', args.secret_name, '--ignore-not-found', '-o', 'name'],
                          capture_output=True, text=True, check=True)
if existing.stdout.strip():
    print('Preserved existing login Secret: ' + args.namespace + '/' + args.secret_name)
else:
    password = secrets.token_urlsafe(24) + 'Aa1!' if args.generate else getpass.getpass('Linux console password: ')
    if len(password) < 12:
        parser.error('Use a password of at least 12 characters')
    obj = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque', 'metadata': {
        'name': args.secret_name, 'namespace': args.namespace,
        'labels': {'demo': 'vm-islands'}, 'annotations': {'demo.openshift.io/login-user': args.username}},
        'stringData': {args.username: password}}
    subprocess.run(base + ['create', '-f', '-'], input=json.dumps(obj),
                   capture_output=True, text=True, check=True)
    print('Created ' + args.namespace + '/' + args.secret_name + '; password was not logged or written locally')
print('Console username: ' + args.username + '. Reveal its password from the matching key in the Secret view.')
