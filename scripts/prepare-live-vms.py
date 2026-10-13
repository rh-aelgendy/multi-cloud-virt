#!/usr/bin/env python3
"""Prepare durable ARO prerequisites for the live ApplicationSet; deploy no VMs."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--context', required=True)
p.add_argument('--pipeline-run', default='windows11-developer-customize-j6wd8')
a = p.parse_args()
base = ['oc', '--context', a.context]
def oc(*args):
    return subprocess.run(base+list(args), text=True, capture_output=True, check=True).stdout
run = json.loads(oc('-n','image-factory','get','pipelinerun',a.pipeline_run,'-o','json'))
if not any(c['type']=='Succeeded' and c['status']=='True' for c in run['status'].get('conditions',[])):
    raise SystemExit('The image PipelineRun must have completed successfully')
image = next((r['value'] for r in run['status'].get('results',[]) if r['name']=='golden-image'),None)
if image != 'win11-dev-v1-1-0':
    raise SystemExit('This checked-in Windows overlay expects win11-dev-v1-1-0; align its sourceRef with the successful pipeline result first')
ds = json.loads(oc('-n','image-factory','get','datasource',image,'-o','json'))
if not any(c['type']=='Ready' and c['status']=='True' for c in ds['status'].get('conditions',[])):
    raise SystemExit('Golden DataSource is not Ready')
for ns in ('linux-vms-prod','windows-vms-vdi'):
    oc('get','namespace',ns,'-o','name')
oc('apply','-f',str(ROOT/'applicationsets/vms/prerequisites.yaml'))
oc('apply','-f',str(ROOT/'examples/windows-vms-vdi/clone-permissions.aro.yaml'))
oc('apply','-f',str(ROOT/'applicationsets/vms/project.yaml'))
# Reuse the existing durable ARO credential; change only its namespace allowlist.
name = 'team-x-cluster-acm-hub-aro'
encoded = oc('-n','openshift-gitops','get','secret',name,'-o','jsonpath={.data.namespaces}')
namespaces = set(base64.b64decode(encoded).decode().split(','))
namespaces.update(('linux-vms-prod','windows-vms-vdi'))
oc('-n','openshift-gitops','patch','secret',name,'--type=merge','-p',json.dumps({'stringData':{'namespaces':','.join(sorted(namespaces))}}))
subprocess.run([sys.executable,str(ROOT/'scripts/create-linux-login-secret.py'),'--context',a.context,'--namespace','linux-vms-prod','--generate'],check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/create-windows11-login.py'),'--context',a.context,'--namespace','windows-vms-vdi','--secret-name','win11-gitops-01-answer','--hostname','WIN11-GITOPS-01','--generate'],check=True)
print('Prepared ARO-only live GitOps prerequisites; no ApplicationSet or VM deployed')
