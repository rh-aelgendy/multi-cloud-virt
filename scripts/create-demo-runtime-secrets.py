#!/usr/bin/env python3
"""Create durable, unique demo VM credentials directly in each cluster; never log passwords."""
import argparse
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--aro-context', required=True)
parser.add_argument('--rosa-context', required=True)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('create-runtime-secret.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
for context, cloud, hostname in [(args.aro_context, 'azure', 'TEAMX-AZ-01'),
                                 (args.rosa_context, 'aws', 'TEAMX-AWS-01')]:
    name = 'team-x-win-v100-answer'
    exists = subprocess.run(['oc', '--context', context, '-n', 'team-x', 'get', 'secret', name,
                             '--ignore-not-found', '-o', 'name'], capture_output=True, text=True, check=True)
    if exists.stdout.strip():
        print('Preserved existing runtime Secret on ' + cloud)
        continue
    password = secrets.token_urlsafe(24) + 'Aa1!'
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': 'team-x',
               'labels': {'demo': 'vm-islands'}}, 'stringData': {
               'unattend.xml': runtime.answer(hostname, cloud, password, 'v1.0.0'),
               'specialize.ps1': runtime.specialize_script(cloud, 'v1.0.0', hostname),
               'username': 'Administrator', 'password': password}}
    subprocess.run(['oc', '--context', context, 'create', '-f', '-'], input=json.dumps(secret),
                   capture_output=True, text=True, check=True)
    print('Created unique runtime credential on ' + cloud + '; reveal only in its Console Secret view')
