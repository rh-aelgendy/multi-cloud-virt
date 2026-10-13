#!/usr/bin/env python3
"""Register two namespace-scoped destinations in ARO GitOps; tokens never leave stdin/memory."""
import argparse
import base64
import json
from pathlib import Path
import ssl
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--aro-context', required=True)
parser.add_argument('--rosa-context', required=True)
args = parser.parse_args()


def oc(context, *commands, obj=None):
    result = subprocess.run(['oc', '--context', context, *commands],
                            input=json.dumps(obj) if obj else None,
                            capture_output=True, text=True, check=True, timeout=120)
    return result.stdout


for context, name, image_namespace in [(args.aro_context, 'acm-hub-aro', 'image-factory'),
                                       (args.rosa_context, 'rosa-virt-dr', 'team-x-images')]:
    oc(context, 'apply', '-f', str(ROOT / 'vm/base/namespace.yaml'))
    oc(context, 'apply', '-f', str(ROOT / 'gitops/runtime-rbac.yaml'))
    oc(context, 'apply', '-f', '-', obj={'apiVersion': 'v1', 'kind': 'Namespace',
                                      'metadata': {'name': image_namespace}})
    text = (ROOT / 'gitops/clone-rbac.yaml').read_text().replace('namespace: image-factory', 'namespace: ' + image_namespace)
    subprocess.run(['oc', '--context', context, 'apply', '-f', '-'], input=text,
                   capture_output=True, text=True, check=True, timeout=120)
    # User requested a durable lab. Kubernetes binds this legacy token to the
    # dedicated namespace-scoped ServiceAccount; delete the Secret/SA to revoke.
    credential = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/service-account-token',
                  'metadata': {'name': 'team-x-gitops-token', 'namespace': 'team-x',
                               'annotations': {'kubernetes.io/service-account.name': 'team-x-gitops'},
                               'labels': {'demo': 'vm-islands'}}}
    oc(context, 'apply', '-f', '-', obj=credential)
    for _ in range(30):
        generated = json.loads(oc(context, '-n', 'team-x', 'get', 'secret', 'team-x-gitops-token', '-o', 'json'))
        if generated.get('data', {}).get('token'):
            break
        time.sleep(2)
    else:
        raise TimeoutError('ServiceAccount token controller did not populate the demo Secret')
    token = base64.b64decode(generated['data']['token']).decode()
    cfg = json.loads(oc(context, 'config', 'view', '--minify', '--raw', '-o', 'json'))
    server = cfg['clusters'][0]['cluster']['server']
    pem = base64.b64decode(generated['data'].get('ca.crt', '')).decode()
    # Include public roots as well as the cluster API roots. Validate before registration.
    default_ca = ssl.get_default_verify_paths().cafile
    if default_ca:
        pem += '\n' + Path(default_ca).read_text()
    if cfg['clusters'][0]['cluster'].get('certificate-authority-data'):
        pem += '\n' + base64.b64decode(cfg['clusters'][0]['cluster']['certificate-authority-data']).decode()
    request = urllib.request.Request(server + '/version', headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, context=ssl.create_default_context(cadata=pem), timeout=30) as response:
        if response.status != 200:
            raise RuntimeError('API trust validation failed for ' + name)
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': 'team-x-cluster-' + name, 'namespace': 'openshift-gitops',
        'labels': {'argocd.argoproj.io/secret-type': 'cluster', 'demo': 'vm-islands'},
        'annotations': {'demo.openshift.io/token-lifetime': 'Until revoked; bound to team-x/team-x-gitops'}},
        'stringData': {'name': name, 'server': server, 'namespaces': 'team-x', 'clusterResources': 'false',
                       'config': json.dumps({'bearerToken': token, 'tlsClientConfig': {
                           'insecure': False, 'caData': base64.b64encode(pem.encode()).decode()}})}}
    # Avoid storing the CA bundle and credential twice in a last-applied annotation.
    oc(args.aro_context, 'apply', '--server-side', '--field-manager=team-x-demo', '-f', '-', obj=secret)
    print('Registered ' + name + ' in ARO GitOps (team-x namespace only, TLS verified, valid until revoked)')
