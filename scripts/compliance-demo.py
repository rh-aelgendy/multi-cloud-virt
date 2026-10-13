#!/usr/bin/env python3
"""Inspect, rehearse or reset only the three ACM compliance demo scenarios."""
import argparse
import json
import subprocess
import time

POLICIES = ['demo-01-project-ownership', 'demo-02-vm-capacity', 'demo-03-golden-image-catalog']
PROJECTS = ['linux-vms-prod', 'windows-vms-vdi']
HUB_NAMESPACE = 'vm-demo-policies'


def oc(context, *args, obj=None):
    result = subprocess.run(['oc', '--context', context, *args],
                            input=json.dumps(obj) if obj is not None else None,
                            text=True, capture_output=True, check=True, timeout=60)
    return result.stdout


def read(context, *args):
    return json.loads(oc(context, *args, '-o', 'json'))


def wait(check, description, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(3)
    raise TimeoutError(description)


def policy_state(context, expected):
    for name in POLICIES:
        policy = read(context, '-n', HUB_NAMESPACE, 'get', 'policy.policy.open-cluster-management.io', name)
        results = policy.get('status', {}).get('status', [])
        if (policy.get('status', {}).get('compliant') != expected or len(results) != 2
                or {x['clustername'] for x in results} != {'acm-hub-aro', 'rosa-virt-dr'}
                or any(x.get('compliant') != expected for x in results)):
            return False
    return True


def propagated_inform(destinations):
    for context, cluster, _ in destinations:
        for name in POLICIES:
            policy = read(context, '-n', cluster, 'get', 'configurationpolicy', name)
            if policy['spec']['remediationAction'] != 'inform':
                return False
    return True


def mode(context, value):
    for name in POLICIES:
        oc(context, '-n', HUB_NAMESPACE, 'patch', 'policy.policy.open-cluster-management.io', name,
           '--type=merge', '--patch-file=/dev/stdin', obj={'spec': {'remediationAction': value}})


def remove_labels(context, kind, name, namespace, expected):
    prefix = ['-n', namespace] if namespace else []
    resource = read(context, *prefix, 'get', kind, name)
    present = resource['metadata'].get('labels', {})
    keys = [key + '-' for key, value in expected.items() if present.get(key) == value]
    if keys:
        oc(context, *prefix, 'label', kind, name, *keys)


def status(context):
    for name in POLICIES:
        policy = read(context, '-n', HUB_NAMESPACE, 'get', 'policy.policy.open-cluster-management.io', name)
        print(name, policy['spec']['remediationAction'], policy.get('status', {}).get('compliant', 'Pending'))
        for item in policy.get('status', {}).get('status', []):
            print('  ' + item['clustername'] + ': ' + item.get('compliant', 'Pending'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'enforce', 'reset'])
    parser.add_argument('--aro-context', required=True)
    parser.add_argument('--rosa-context', required=True)
    args = parser.parse_args()
    destinations = [(args.aro_context, 'acm-hub-aro', 'image-factory'),
                    (args.rosa_context, 'rosa-virt-dr', 'team-x-images')]
    if args.action == 'enforce':
        mode(args.aro_context, 'enforce')
        wait(lambda: policy_state(args.aro_context, 'Compliant'), 'Both clusters did not become compliant')
    elif args.action == 'reset':
        mode(args.aro_context, 'inform')
        wait(lambda: propagated_inform(destinations), 'Inform mode did not propagate; no resources reset')
        for context, _, image_namespace in destinations:
            for project in PROJECTS:
                remove_labels(context, 'namespace', project, None,
                              {'demo.openshift.io/owner': 'team-x', 'demo.openshift.io/cost-center': 'virt-demo'})
                oc(context, '-n', project, 'delete', 'resourcequota', 'demo-vm-capacity', '--ignore-not-found')
            remove_labels(context, 'datasource', 'team-x-windows-v1-0-0', image_namespace,
                          {'demo.openshift.io/catalog-owner': 'team-x', 'demo.openshift.io/lifecycle': 'golden'})
        wait(lambda: policy_state(args.aro_context, 'NonCompliant'), 'Both clusters did not return to the demo starting state')
    status(args.aro_context)


if __name__ == '__main__':
    main()
