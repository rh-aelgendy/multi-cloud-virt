#!/usr/bin/env python3
"""Create demo private Azure Blob storage; keep all credentials in Kubernetes."""
import hashlib,json,subprocess,pathlib

def run(args,stdin=None):
 p=subprocess.run(args,input=stdin,text=True,capture_output=True)
 if p.returncode:raise RuntimeError('Command failed: '+args[0]+' '+args[1]+' (output withheld to protect credentials)')
 return p.stdout
ns='open-cluster-management-observability'
subscription=json.loads(run(['az','account','show','-o','json']))['id']
account='vmobs'+hashlib.sha256((subscription+'multi-cloud-virt').encode()).hexdigest()[:18]
group='rg-multi-cloud-virt-observability'
run(['az','group','create','-n',group,'-l','westeurope','--tags','demo=multi-cloud-virt','-o','none'])
run(['az','storage','account','create','-g',group,'-n',account,'-l','westeurope','--sku','Standard_LRS','--kind','StorageV2','--https-only','true','--min-tls-version','TLS1_2','--allow-blob-public-access','false','--tags','demo=multi-cloud-virt','-o','none'])
key=json.loads(run(['az','storage','account','keys','list','-g',group,'-n',account,'-o','json']))[0]['value']
run(['az','storage','container','create','--account-name',account,'--account-key',key,'--name','metrics','--public-access','off','-o','none'])
run(['oc','apply','-f','-'],json.dumps({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}}))
config='type: AZURE\nconfig:\n  storage_account: '+account+'\n  storage_account_key: '+key+'\n  container: metrics\n  endpoint: blob.core.windows.net\n'
run(['oc','apply','-f','-'],json.dumps({'apiVersion':'v1','kind':'Secret','metadata':{'name':'vm-observability-object-storage','namespace':ns},'stringData':{'thanos.yaml':config}}))
pull=json.loads(run(['oc','get','secret','pull-secret','-n','openshift-config','-o','json']))
run(['oc','apply','-f','-'],json.dumps({'apiVersion':'v1','kind':'Secret','metadata':{'name':'vm-observability-pull-secret','namespace':ns},'type':pull['type'],'data':pull['data']}))
record={'resourceGroup':group,'storageAccount':account,'container':'metrics','namespace':ns,'secret':'vm-observability-object-storage','credentials':'Kubernetes only; no SAS expiry'}
path=pathlib.Path('.local/demo/vm-observability-storage.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(record,indent=2)+'\n')
print('Private Blob backend ready; credentials stored only in Kubernetes. Resource group: '+group)
