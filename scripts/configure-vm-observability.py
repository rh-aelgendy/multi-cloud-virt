#!/usr/bin/env python3
"""Attach demo VM metrics and install the dashboard after ACM installs its APIs."""
import copy,json,subprocess

def oc(*args,obj=None):
 p=subprocess.run(['oc',*args],input=json.dumps(obj) if obj is not None else None,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 return p.stdout
ref={'group':'monitoring.rhobs','resource':'scrapeconfigs','namespace':'open-cluster-management-observability','name':'vm-fleet-metrics'}
with open('observability/scrapeconfig.json') as stream:scrape=json.load(stream)
oc('apply','--dry-run=server','-f','-',obj=scrape)
oc('apply','-f','-',obj=scrape)
addon=json.loads(oc('get','clustermanagementaddon','multicluster-observability-addon','-o','json'))
placements=copy.deepcopy(addon['spec']['installStrategy']['placements'])
if not placements:raise RuntimeError('MCOA metrics placements are not ready yet')
for placement in placements:
 configs=placement.setdefault('configs',[])
 if ref not in configs:configs.append(ref)
patch=[{'op':'test','path':'/metadata/resourceVersion','value':addon['metadata']['resourceVersion']},{'op':'replace','path':'/spec/installStrategy/placements','value':placements}]
oc('patch','clustermanagementaddon','multicluster-observability-addon','--type=json','-p',json.dumps(patch),'--dry-run=server')
oc('patch','clustermanagementaddon','multicluster-observability-addon','--type=json','-p',json.dumps(patch))
crd=json.loads(oc('get','crd','persesdashboards.perses.dev','-o','json'))
served=[v['name'] for v in crd['spec']['versions'] if v['served']]
with open('observability/dashboard.json') as stream:dashboard=json.load(stream)
if 'v1alpha2' not in served:
 if 'v1alpha1' not in served:raise RuntimeError('Unsupported PersesDashboard API')
 dashboard['apiVersion']='perses.dev/v1alpha1';dashboard['spec']=dashboard['spec']['config']
oc('apply','--dry-run=server','-f','-',obj=dashboard)
oc('apply','-f','-',obj=dashboard)
print('VM metric scrape attached without replacing other configs; Perses dashboard applied.')
