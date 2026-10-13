"""ARO-only Windows 11 image preparation, validation and publication."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
from xml.sax.saxutils import escape

NS = os.environ['NAMESPACE']
BUILD = os.environ['BUILD_ID']
IMAGE = os.environ['IMAGE_NAME']
VERSION = os.environ['IMAGE_VERSION']
MODE = os.environ['MODE']


def oc(*args, obj=None):
    return subprocess.run(['oc', '-n', NS, *args], input=json.dumps(obj) if obj is not None else None,
                          text=True, capture_output=True, check=True, timeout=90).stdout


def get(kind, name):
    data = oc('get', kind, name, '--ignore-not-found', '-o', 'json')
    return json.loads(data) if data.strip() else None


def create(kind, api, name, **fields):
    obj = {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': NS,
           'labels': {'demo': 'windows11-developer', 'image-version': VERSION}}, **fields}
    oc('create', '-f', '-', obj=obj)


def wait(check, timeout=5400):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(5)
    raise TimeoutError('Windows 11 image operation timed out')


def prepare():
    if os.environ['ACCEPT_EULA'] != 'true':
        raise ValueError('Accept the applicable Microsoft license terms before running this pipeline')
    for name in (BUILD, IMAGE):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,50}', name):
            raise ValueError('Use a short lowercase Kubernetes resource name')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', VERSION):
        raise ValueError('Use an image version such as v1.0.0')
    if MODE not in ('base', 'developer'):
        raise ValueError('Invalid image mode')
    if any(get(k, n) for k, n in [('vm', BUILD), ('dv', BUILD+'-root'), ('datasource', IMAGE)]):
        raise ValueError('Build/output already exists; use a fresh build ID and image name')
    if MODE == 'developer':
        source = get('datasource', os.environ['SOURCE_IMAGE'])
        if not source or not any(c['type'] == 'Ready' and c['status'] == 'True' for c in source.get('status', {}).get('conditions', [])):
            raise ValueError('Source Windows 11 DataSource must be ready')
        if source['metadata'].get('labels', {}).get('demo.openshift.io/os') != 'windows11':
            raise ValueError('Source must be a validated Windows 11 base image')
    software = json.loads(Path('/opt/source/software.json').read_text())
    script = Path('/opt/source/customize.ps1').read_text()
    for key, value in {'@MODE@': MODE, '@IMAGE_VERSION@': VERSION, '@VSCODE_URL@': software['url'],
                       '@VSCODE_SHA256@': software['sha256hash'], '@VSCODE_VERSION@': software['productVersion']}.items():
        script = script.replace(key, value)
    xml = Path('/opt/source/base-autounattend.xml' if MODE == 'base' else '/opt/source/customize-unattend.xml').read_text()
    xml = xml.replace('@EDITION@', escape(os.environ['WINDOWS_EDITION'])).replace('<AcceptEula>false</AcceptEula>', '<AcceptEula>true</AcceptEula>')
    key = 'autounattend.xml' if MODE == 'base' else 'unattend.xml'
    create('ConfigMap', 'v1', BUILD+'-answer', data={key: xml, 'customize.ps1': script})
    if MODE == 'base':
        url = os.environ['ISO_URL']
        iso_name = os.environ['ISO_DV_NAME']
        media = get('dv', iso_name)
        if media:
            if media['metadata'].get('labels', {}).get('demo') != 'windows11-developer':
                raise ValueError('Reuse only Windows 11 media imported by this pipeline')
            if url and media['spec'].get('source', {}).get('http', {}).get('url') != url:
                raise ValueError('Existing ISO media has a different source URL; choose a new ISO DataVolume name')
        elif not url.startswith('https://') or 'REPLACE' in url:
            raise ValueError('Supply a Windows 11 ISO HTTPS URL, or reuse already imported ISO media')
        storage = {'storageClassName': 'anf', 'accessModes': ['ReadWriteMany'], 'volumeMode': 'Filesystem',
                   'resources': {'requests': {'storage': '80Gi'}}}
        create('DataVolume', 'cdi.kubevirt.io/v1beta1', BUILD+'-root', spec={'source': {'blank': {}}, 'storage': storage})
        storage = {**storage, 'resources': {'requests': {'storage': '10Gi'}}}
        if not media:
            create('DataVolume', 'cdi.kubevirt.io/v1beta1', iso_name, spec={'source': {'http': {'url': url}}, 'storage': storage})
        def imported():
            phase = (get('dv', iso_name) or {}).get('status', {}).get('phase')
            if phase == 'Failed':
                raise RuntimeError('ISO import failed')
            return phase == 'Succeeded'
        wait(imported, 3600)
    print('Prepared '+MODE+' image build on ARO', flush=True)


def validate():
    create('Service', 'v1', BUILD, spec={'selector': {'image-builder': BUILD},
           'ports': [{'name': 'validation', 'port': 8080, 'targetPort': 8080}]})
    def evidence():
        vmi = get('vmi', BUILD)
        if (vmi or {}).get('status', {}).get('phase') in ('Failed', 'Succeeded'):
            raise RuntimeError('Builder stopped before validation evidence was captured')
        try:
            with urllib.request.urlopen('http://'+BUILD+':8080/validation.json', timeout=5) as response:
                result = json.loads(response.read().decode('utf-8-sig'))
        except (OSError, ValueError):
            return None
        expected = {'windows11', 'virtio-tools', 'guest-agent'}
        if MODE == 'developer':
            expected.update({'vscode-system-install', 'vscode-cli', 'sample-project', 'desktop-shortcuts'})
        if (result.get('passed') is not True or result.get('version') != VERSION or result.get('mode') != MODE
                or set(result.get('checks', [])) != expected):
            raise RuntimeError('Guest validation failed')
        if not any(c['type'] == 'AgentConnected' and c['status'] == 'True' for c in vmi.get('status', {}).get('conditions', [])):
            return None
        return result
    result = wait(evidence)
    create('ConfigMap', 'v1', IMAGE+'-evidence', data={'validation.json': json.dumps(result, indent=2)})
    print(json.dumps(result), flush=True)


def publish():
    evidence = get('configmap', IMAGE+'-evidence')
    result = json.loads((evidence or {}).get('data', {}).get('validation.json', '{}'))
    if result.get('passed') is not True or result.get('version') != VERSION or result.get('mode') != MODE:
        raise RuntimeError('Publication requires matching captured guest evidence')
    vmi = get('vmi', BUILD)
    if not vmi or vmi.get('status', {}).get('phase') != 'Succeeded':
        raise RuntimeError('Publication requires observed Windows shutdown')
    oc('patch', 'vm', BUILD, '--type=merge', '-p', '{"spec":{"runStrategy":"Halted"}}')
    oc('delete', 'vmi', BUILD, '--ignore-not-found', '--wait=true', '--timeout=180s')
    if get('vmi', BUILD):
        raise RuntimeError('Refusing to publish an attached disk')
    create('DataSource', 'cdi.kubevirt.io/v1beta1', IMAGE, spec={'source': {'pvc': {'name': BUILD+'-root', 'namespace': NS}}})
    oc('label', 'datasource', IMAGE, 'demo.openshift.io/os=windows11',
       'instancetype.kubevirt.io/default-preference=windows.11.virtio',
       'instancetype.kubevirt.io/default-preference-kind=VirtualMachineClusterPreference',
       'instancetype.kubevirt.io/default-instancetype=u1.large',
       'instancetype.kubevirt.io/default-instancetype-kind=VirtualMachineClusterInstancetype')
    oc('delete', 'service', BUILD, '--ignore-not-found')
    Path(os.environ['RESULT_IMAGE']).write_text(IMAGE)
    print('Published persistent ARO-only boot source '+IMAGE, flush=True)


if __name__ == '__main__':
    {'prepare': prepare, 'validate': validate, 'publish': publish}[sys.argv[1]]()
