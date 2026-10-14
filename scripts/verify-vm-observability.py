#!/usr/bin/env python3
"""Read-only verification of dashboard PromQL and the two real-metric fixtures."""
import argparse,json,pathlib,subprocess,sys
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context',help='ARO hub oc context; defaults to current context')
parser.add_argument('--require-candidates',action='store_true',help='Fail until both fixture VMs meet the dashboard candidate criteria')
args=parser.parse_args()
base=['oc']+(['--context',args.context] if args.context else [])
base+=['exec','-n','open-cluster-management-observability','deployment/observability-thanos-query','--','curl','-fsSG','http://localhost:9090/api/v1/query','--data-urlencode']
root=pathlib.Path(__file__).resolve().parents[1]
dashboard=json.loads((root/'observability/dashboard.json').read_text())
results={}
for index,panel in dashboard['spec']['config']['panels'].items():
 for n,query in enumerate(panel['spec']['queries']):
  expr=query['spec']['plugin']['spec']['query']
  proc=subprocess.run(base+['query='+expr],capture_output=True,text=True,check=True)
  value=json.loads(proc.stdout)
  if value['status']!='success':raise RuntimeError('PromQL failed: '+panel['spec']['display']['name'])
  results[(index,n)]=value['data']['result']
def lookup(panel,cluster,name):
 values=[float(x['value'][1]) for x in results[(panel,0)] if x['metric'].get('cluster')==cluster and x['metric'].get('name')==name]
 return values[0] if len(values)==1 else None
ok=True
for cloud,cluster in [('aro','acm-hub-aro'),('rosa','rosa-virt-dr')]:
 name='linux-oversized-'+cloud
 row={'cluster':cluster,'vm':name,'assignedVCPU':lookup('0',cluster,name),'cpuPercent':lookup('2',cluster,name),'guestMemoryPercent':lookup('3',cluster,name),'samples15m':lookup('6',cluster,name),'candidate':lookup('4',cluster,name)==1}
 print(json.dumps(row))
 if any(row[x] is None for x in ['assignedVCPU','cpuPercent','guestMemoryPercent','samples15m']):ok=False
 if args.require_candidates and not row['candidate']:ok=False
if not ok:sys.exit('Telemetry is missing or the requested candidate history is not ready yet.')
print('All dashboard queries passed; both fixture VM telemetry streams verified.')
