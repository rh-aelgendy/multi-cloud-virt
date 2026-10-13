#!/usr/bin/env bash
set -euo pipefail
context=${1:?Usage: preflight.sh CONTEXT [build]}
oc --context "$context" version
oc --context "$context" get nodes -L node.kubernetes.io/instance-type,kubevirt.io/schedulable
oc --context "$context" get storageclasses
oc --context "$context" get storageprofiles.cdi.kubevirt.io
oc --context "$context" get hyperconverged -n openshift-cnv
oc --context "$context" get crd virtualmachines.kubevirt.io datavolumes.cdi.kubevirt.io virtualmachineexports.export.kubevirt.io
if [[ ${2:-} == build ]]; then
  oc --context "$context" get crd pipelines.tekton.dev tasks.tekton.dev
  oc --context "$context" get configmap hubresolver-config -n openshift-pipelines -o yaml
fi
