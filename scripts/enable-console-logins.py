#!/usr/bin/env python3
"""Opt-in lab-only VM credential display. Copies existing Secret values into live VM YAML, never Git."""
import argparse,base64,json,re,subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--apply',action='store_true',help='Copy passwords into VM resources, readable by VM readers; default only lists targets')
p.add_argument('--vm',action='append',help='Only these VM names; repeat as needed')
a=p.parse_args()
contexts={'aro':'default/api-gbxlsummit8e0p-westeurope-aroapp-io:6443/kube:admin','rosa':'default/api-g-bxl-summit-dp4i-p3-openshiftapps-com:443/rosa-admin'}
targets=[]
for c in contexts:
 targets.extend([(c,'team-x','team-x-linux','linux-vm-login','fedora','fedora'),(c,'team-x','team-x-win-v100','team-x-win-v100-answer','password','Administrator'),(c,'linux-vms-prod','linux-oversized-'+c,'linux-vm-login','fedora','fedora')])
targets.extend([('aro','windows-vms-vdi','win11-dev-01','win11-dev-01-answer','password','demo'),('aro','linux-vms-prod','linux-gitops-01','linux-vm-login','fedora','fedora'),('aro','windows-vms-vdi','win11-gitops-01','win11-gitops-01-answer','password','demo')])
def run(args,payload=None):
 r=subprocess.run(args,input=payload,capture_output=True,text=True)
 if r.returncode:raise RuntimeError('Cluster request failed; credential-bearing output withheld')
 return r.stdout
for cloud,ns,name,secret,key,username in targets:
 if a.vm and name not in a.vm:continue
 if not a.apply:
  print('Plan: '+cloud+'/'+ns+'/'+name+' <- Secret '+secret);continue
 base=['oc','--context',contexts[cloud],'-n',ns]
 raw=run(base+['get','vm',name,'--ignore-not-found','-o','json'])
 if not raw.strip():print('Skipped absent VM: '+cloud+'/'+ns+'/'+name);continue
 vm=json.loads(raw);data=json.loads(run(base+['get','secret',secret,'-o','json']))['data']
 password=base64.b64decode(data[key]).decode()
 if 'username' in data:username=base64.b64decode(data['username']).decode()
 volumes=vm['spec']['template']['spec']['volumes'];source=next((v.get('cloudInitNoCloud',v.get('cloudInitConfigDrive')) for v in volumes if 'cloudInitNoCloud' in v or 'cloudInitConfigDrive' in v),None)
 if source is None:
  source={'userData':'#cloud-config\n'};volumes.append({'name':'console-login-display','cloudInitNoCloud':source})
 text=source.get('userData','#cloud-config\n')
 text=re.sub(r'^(user|password):[^\n]*\n?','',text,flags=re.MULTILINE)
 text=text.rstrip()+'\nuser: '+json.dumps(username)+'\npassword: '+json.dumps(password)+'\n'
 if not re.search(r'^chpasswd:',text,re.MULTILINE):text+='chpasswd:\n  expire: false\n'
 parsed=json.loads(run(['ruby','-ryaml','-rjson','-e','d=YAML.safe_load(STDIN.read); puts JSON.generate([d["user"],d["password"]])'],text))
 assert parsed==[username,password], 'Console credential YAML parsing failed'
 source['userData']=text
 patch=[{'op':'test','path':'/metadata/resourceVersion','value':vm['metadata']['resourceVersion']},{'op':'replace','path':'/spec/template/spec/volumes','value':volumes}]
 cmd=base+['patch','vm',name,'--type=json','--patch-file=/dev/stdin']
 run(cmd+['--dry-run=server'],json.dumps(patch));run(cmd,json.dumps(patch))
 # Verify the exact fields consumed by release-4.21 console, without printing credentials.
 current=json.loads(run(base+['get','vm',name,'-o','json']))
 sv=next(v.get('cloudInitNoCloud',v.get('cloudInitConfigDrive')) for v in current['spec']['template']['spec']['volumes'] if 'cloudInitNoCloud' in v or 'cloudInitConfigDrive' in v)
 assert '\nuser: '+json.dumps(username)+'\npassword: '+json.dumps(password)+'\n' in sv['userData']
 print('Verified console login fields: '+cloud+'/'+ns+'/'+name+' (no restart performed)')
