#!/usr/bin/env python3
"""Verify a two-VM quota with halted, diskless admission probes; always clean them up."""
import argparse
import json
import subprocess
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context', required=True)
parser.add_argument('--namespace', default='linux-vms-prod')
args = parser.parse_args()
cmd = ['oc', '--context', args.context, '-n', args.namespace]
quota = json.loads(subprocess.run(cmd + ['get', 'resourcequota', 'demo-vm-capacity', '-o', 'json'],
                                   text=True, capture_output=True, check=True).stdout)
key = 'count/virtualmachines.kubevirt.io'
if quota['spec']['hard'].get(key) != '2' or quota.get('status', {}).get('used', {}).get(key) != '0':
    raise SystemExit('Requires the demo two-VM quota and an empty project; no probes created')
created = []
prefix = 'quota-check-' + uuid.uuid4().hex[:8]
try:
    for index in range(1, 4):
        name = prefix + '-' + str(index)
        vm = {'apiVersion': 'kubevirt.io/v1', 'kind': 'VirtualMachine',
              'metadata': {'name': name, 'namespace': args.namespace, 'labels': {'demo': 'quota-admission-check'}},
              'spec': {'runStrategy': 'Halted', 'template': {'spec': {
                  'domain': {'devices': {}, 'resources': {'requests': {'memory': '128Mi'}}}}}}}
        operation = ['create', '-f', '-'] + (['--dry-run=server'] if index == 3 else [])
        result = subprocess.run(cmd + operation, input=json.dumps(vm), text=True, capture_output=True)
        if index < 3:
            if result.returncode:
                raise RuntimeError(result.stderr)
            created.append(name)
        else:
            if result.returncode == 0 or 'exceeded quota' not in result.stderr or key not in result.stderr:
                raise RuntimeError('Expected the third VM to be denied by the VM count quota: ' + result.stderr)
            print('PASS: two halted definitions admitted; third VM denied by quota. No VMI or disk created.')
finally:
    if created:
        subprocess.run(cmd + ['delete', 'vm', *created, '--wait=true', '--timeout=60s'],
                       text=True, capture_output=True, check=True)
        print('Removed only the temporary admission probes.')
