"""Demo image controller. Runs inside the toolbox task; all writes are namespace scoped."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request


def oc(*args, obj=None):
    result = subprocess.run(
        ['oc', '-n', os.environ['NAMESPACE'], *args],
        input=json.dumps(obj) if obj is not None else None,
        text=True, capture_output=True, check=True, timeout=90,
    )
    return result.stdout


def get(kind, name):
    text = oc('get', kind, name, '--ignore-not-found', '-o', 'json')
    return json.loads(text) if text.strip() else None


def create(obj):
    # Never silently replace a disk, a completed image, or an existing build.
    oc('create', '-f', '-', obj=obj)


def wait_for(check, description, timeout=3600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(5)
    raise TimeoutError(description)


def metadata(name):
    return {'name': name, 'labels': {'demo': 'vm-islands', 'team': 'team-x', 'build-id': build_id}}


def dv(name, source, size):
    return {'apiVersion': 'cdi.kubevirt.io/v1beta1', 'kind': 'DataVolume',
            'metadata': metadata(name), 'spec': {'source': source, 'storage': {
                'storageClassName': os.environ['STORAGE_CLASS'],
                'volumeMode': 'Filesystem', 'accessModes': ['ReadWriteMany'],
                'resources': {'requests': {'storage': size}}}}}


def prepare():
    if os.environ['ACCEPT_EULA'] != 'true':
        raise ValueError('Set accept-eula=true only after accepting the Microsoft license terms.')
    if not os.environ['ISO_URL'].startswith('https://') or 'REPLACE' in os.environ['ISO_URL']:
        raise ValueError('Supply an HTTPS URL for your Windows Server 2022 English ISO')
    for key in ('STORAGE_CLASS', 'VIRTIO_IMAGE'):
        if not os.environ[key] or 'REPLACE' in os.environ[key]:
            raise ValueError(f'Configure {key}')
    xml = Path('/opt/windows/autounattend.xml').read_text().replace(
        '<AcceptEula>false</AcceptEula>', '<AcceptEula>true</AcceptEula>')
    ps = Path('/opt/windows/post-install.ps1').read_text().replace('@IMAGE_VERSION@', version)
    create({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': metadata(build_id + '-answer'),
            'data': {'autounattend.xml': xml, 'post-install.ps1': ps}})
    create(dv(build_id + '-root', {'blank': {}}, '64Gi'))
    create(dv(build_id + '-iso', {'http': {'url': os.environ['ISO_URL']}}, '9Gi'))
    print('Waiting for the Windows ISO import', flush=True)
    def imported():
        obj = get('dv', build_id + '-iso')
        phase = (obj or {}).get('status', {}).get('phase')
        if phase == 'Failed':
            raise RuntimeError('Windows ISO import failed')
        return phase == 'Succeeded'
    wait_for(imported, 'Windows ISO import did not finish', 2400)
    print('ISO imported; root disk and answer media prepared', flush=True)


def install():
    # E: is the VirtIO CD; F: is the sysprep CD, matching the answer file.
    disks = [
        {'name': 'root', 'bootOrder': 1, 'disk': {'bus': 'virtio'}},
        {'name': 'install', 'bootOrder': 2, 'cdrom': {'bus': 'sata'}},
        {'name': 'drivers', 'cdrom': {'bus': 'sata'}},
        {'name': 'answer', 'cdrom': {'bus': 'sata'}},
    ]
    create({'apiVersion': 'kubevirt.io/v1', 'kind': 'VirtualMachine',
            'metadata': metadata(build_id), 'spec': {
                'runStrategy': 'RerunOnFailure',
                'template': {'metadata': {'labels': {'factory-vm': build_id}}, 'spec': {
                    'nodeSelector': {'workload': 'virt'},
                    'domain': {
                        'cpu': {'cores': 4}, 'resources': {'requests': {'memory': '8Gi'}},
                        'machine': {'type': 'q35'},
                        'firmware': {'bootloader': {'efi': {'secureBoot': False}}},
                        'features': {'acpi': {}, 'apic': {}, 'hyperv': {
                            'relaxed': {}, 'vapic': {}, 'spinlocks': {'spinlocks': 8191}}},
                        'clock': {'utc': {}, 'timer': {'hpet': {'present': False}, 'hyperv': {}}},
                        'devices': {'disks': disks, 'interfaces': [
                            {'name': 'default', 'model': 'virtio', 'masquerade': {}}]}},
                    'networks': [{'name': 'default', 'pod': {}}],
                    'volumes': [
                        {'name': 'root', 'dataVolume': {'name': build_id + '-root'}},
                        {'name': 'install', 'dataVolume': {'name': build_id + '-iso'}},
                        {'name': 'drivers', 'containerDisk': {'image': os.environ['VIRTIO_IMAGE']}},
                        {'name': 'answer', 'sysprep': {'configMap': {'name': build_id + '-answer'}}},
                    ]}}}})
    create({'apiVersion': 'v1', 'kind': 'Service', 'metadata': metadata(build_id),
            'spec': {'selector': {'factory-vm': build_id},
                     'ports': [{'name': 'http', 'port': 80, 'targetPort': 80}]}})
    print('Waiting for Windows install and guest validation (typically 30–60 minutes)', flush=True)

    def guest_evidence():
        vmi = get('vmi', build_id)
        phase = (vmi or {}).get('status', {}).get('phase')
        if phase in ('Failed', 'Succeeded'):
            raise RuntimeError(f'VM stopped before validation was captured: {phase}')
        try:
            with urllib.request.urlopen(f'http://{build_id}/validation.json', timeout=5) as response:
                evidence = json.loads(response.read().decode('utf-8-sig'))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None
        expected = {'virtio-msi', 'guest-agent', 'iis-service', 'http-200'}
        if (evidence.get('passed') is not True or evidence.get('version') != version
                or evidence.get('team') != 'team-x' or set(evidence.get('checks', [])) != expected):
            raise RuntimeError('Guest evidence failed validation')
        return evidence

    evidence = wait_for(guest_evidence, 'Windows did not produce validation evidence', 5400)
    Path(os.environ['WORKSPACE'], 'validation.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence), flush=True)

    def sealed():
        vmi = get('vmi', build_id)
        phase = (vmi or {}).get('status', {}).get('phase')
        if phase in ('Failed', 'Unknown'):
            raise RuntimeError(f'Windows build failed: {phase}')
        return phase == 'Succeeded'

    wait_for(sealed, 'Sysprep did not shut down the VM', 900)
    oc('patch', 'vm', build_id, '--type=merge', '-p', '{"spec":{"runStrategy":"Halted"}}')
    # Keep sealed disk and VM for review; detach before export. Halted stops/removes the VMI.
    oc('delete', 'vmi', build_id, '--ignore-not-found', '--wait=true', '--timeout=180s')
    print('Validated guest and observed shutdown; sealed disk detached', flush=True)


def image_name():
    return 'team-x-windows-' + version.replace('.', '-')


def windows_source_labels():
    return {'demo': 'vm-islands', 'image-version': version,
            'instancetype.kubevirt.io/default-instancetype': 'u1.large',
            'instancetype.kubevirt.io/default-instancetype-kind': 'VirtualMachineClusterInstancetype',
            'instancetype.kubevirt.io/default-preference': 'windows.2k22.virtio',
            'instancetype.kubevirt.io/default-preference-kind': 'VirtualMachineClusterPreference'}


def preflight():
    import xml.etree.ElementTree as ET
    ET.parse('/opt/windows/autounattend.xml')
    checks = [('virtualmachines', os.environ['NAMESPACE']),
              ('datavolumes', os.environ['NAMESPACE']),
              ('datasources', os.environ['NAMESPACE']),
              ('virtualmachineexports', os.environ['NAMESPACE']),
              ('manifestworks.work.open-cluster-management.io', os.environ['DR_CLUSTER'])]
    for resource, namespace in checks:
        answer = oc('-n', namespace, 'auth', 'can-i', 'create', resource).strip()
        if answer != 'yes':
            raise RuntimeError('Missing create permission: ' + resource + ' in ' + namespace)
    print('ARO task node: ' + os.environ.get('NODE_NAME', 'unknown'), flush=True)
    print('Passed: toolbox execution, XML parsing, local image RBAC, ACM transfer RBAC', flush=True)
    print('Windows installation and DR image import still require the ISO and EULA input.', flush=True)


def publish():
    evidence = json.loads(Path(os.environ['WORKSPACE'], 'validation.json').read_text())
    if evidence.get('passed') is not True or evidence.get('version') != version:
        raise RuntimeError('Invalid build evidence')
    if get('vmi', build_id) is not None:
        raise RuntimeError('Refusing to publish an attached disk')
    vm = get('vm', build_id)
    if not vm or vm['spec'].get('runStrategy') != 'Halted':
        raise RuntimeError('Builder must be sealed and halted')
    image_metadata = metadata(image_name())
    image_metadata['labels'].update(windows_source_labels())
    create({'apiVersion': 'cdi.kubevirt.io/v1beta1', 'kind': 'DataSource',
            'metadata': image_metadata, 'spec': {'source': {'pvc': {
                'name': build_id + '-root', 'namespace': os.environ['NAMESPACE']}}}})
    create({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': metadata(image_name() + '-evidence'),
            'data': {'validation.json': json.dumps(evidence, indent=2)}})
    Path(os.environ['RESULT_IMAGE']).write_text(image_name())
    print('Published local boot source ' + image_name(), flush=True)


def stage_dr():
    if get('vmi', build_id) is not None:
        raise RuntimeError('Refusing to export an attached golden disk')
    if not get('datasource', image_name()):
        raise RuntimeError('Local image must be published before DR staging')
    token = secrets.token_hex(32)
    token_name = build_id + '-export-token'
    create({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': metadata(token_name),
            'stringData': {'token': token}})
    create({'apiVersion': 'export.kubevirt.io/v1beta1', 'kind': 'VirtualMachineExport',
            'metadata': metadata(build_id), 'spec': {'tokenSecretRef': token_name,
                'ttlDuration': '4h', 'source': {'apiGroup': '', 'kind': 'PersistentVolumeClaim',
                                              'name': build_id + '-root'}}})
    def ready():
        obj = get('virtualmachineexport', build_id)
        if obj and obj.get('status', {}).get('phase') == 'Ready' and obj['status'].get('links', {}).get('external'):
            return obj
        return None
    obj = wait_for(ready, 'Export route did not become ready', 900)
    external = obj['status']['links']['external']
    url = next(f['url'] for v in external['volumes'] for f in v['formats'] if f['format'] == 'gzip')
    source_namespace = 'team-x-images'
    name = image_name()
    manifests = [
        {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name + '-transfer', 'namespace': source_namespace},
         'stringData': {'header': 'x-kubevirt-export-token: ' + token}},
        {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name + '-ca', 'namespace': source_namespace},
         'data': {'ca.pem': external['cert']}},
        {'apiVersion': 'cdi.kubevirt.io/v1beta1', 'kind': 'DataVolume',
         'metadata': {'name': name, 'namespace': source_namespace, 'labels': {'demo': 'vm-islands'}},
         'spec': {'source': {'http': {'url': url, 'secretExtraHeaders': [name + '-transfer'],
                                    'certConfigMap': name + '-ca'}},
                  'storage': {'storageClassName': os.environ['DR_STORAGE_CLASS'],
                              'volumeMode': 'Filesystem', 'accessModes': ['ReadWriteMany'],
                              'resources': {'requests': {'storage': '80Gi'}}}}},
        {'apiVersion': 'cdi.kubevirt.io/v1beta1', 'kind': 'DataSource',
         'metadata': {'name': name, 'namespace': source_namespace, 'labels': windows_source_labels()},
         'spec': {'source': {'pvc': {'name': name, 'namespace': source_namespace}}}},
    ]
    work_name = name + '-image'
    work = {'apiVersion': 'work.open-cluster-management.io/v1', 'kind': 'ManifestWork',
            'metadata': {'name': work_name, 'namespace': os.environ['DR_CLUSTER']},
            'spec': {'workload': {'manifests': manifests}, 'manifestConfigs': [{
                'resourceIdentifier': {'group': 'cdi.kubevirt.io', 'resource': 'datavolumes',
                                       'namespace': source_namespace, 'name': name},
                'feedbackRules': [{'type': 'JSONPaths', 'jsonPaths': [{'name': 'phase', 'path': '.status.phase'}]}]
            }]}}
    # The token is sent to ACM via stdin. Never print the ManifestWork body.
    oc('-n', os.environ['DR_CLUSTER'], 'create', '-f', '-', obj=work)
    print('ACM is staging the image to ROSA local storage', flush=True)
    def imported():
        item = json.loads(oc('-n', os.environ['DR_CLUSTER'], 'get', 'manifestwork', work_name, '-o', 'json'))
        statuses = item.get('status', {}).get('resourceStatus', {}).get('manifests', [])
        for status in statuses:
            for value in status.get('statusFeedbacks', {}).get('values', []):
                phase = value.get('value', {}).get('string')
                if value.get('name') == 'phase':
                    if phase == 'Failed':
                        raise RuntimeError('ROSA image import failed')
                    if phase == 'Succeeded':
                        return True
        return False
    wait_for(imported, 'ROSA local image import did not finish', 5400)
    # Keep the ManifestWork and local golden disk for lifecycle ownership.
    # Remove the one-time header Secret and CA once CDI has completed its copy.
    work['spec']['workload']['manifests'] = [m for m in manifests if m['kind'] not in ('Secret', 'ConfigMap')]
    oc('-n', os.environ['DR_CLUSTER'], 'apply', '-f', '-', obj=work)
    oc('delete', 'virtualmachineexport', build_id, '--wait=true')
    oc('delete', 'secret', token_name)
    Path(os.environ['RESULT_IMAGE']).write_text(image_name())
    print('ROSA local boot source staged; transfer endpoint and credentials removed', flush=True)


if __name__ == '__main__':
    build_id = os.environ['BUILD_ID']
    version = os.environ['IMAGE_VERSION']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', build_id):
        raise ValueError('build-id must be a DNS label of at most 40 characters')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('version must be vMAJOR.MINOR.PATCH')
    actions = {'prepare': prepare, 'install': install, 'publish': publish, 'stage-dr': stage_dr, 'preflight': preflight}
    actions[sys.argv[1]]()
