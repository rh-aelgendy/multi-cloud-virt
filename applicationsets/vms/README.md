# Deploy the GitOps VMs live — ARO

This uses the list-generator and Kustomize-overlay pattern from the [reference ApplicationSet](https://github.com/rh-aelgendy/aro-virt-gitops/blob/main/applicationsets/vm/applicationset-vm.yaml). Both destinations are ARO, with `workload=virt` placement. Windows clones the successful pipeline's local `win11-dev-v1-1-0` golden image; Linux clones the existing Fedora bootable volume.

## Audience steps

1. In ARO Console, select project **openshift-gitops** and click **+ / Import YAML**. Paste [applicationset.yaml](https://raw.githubusercontent.com/rh-aelgendy/multi-cloud-virt/main/applicationsets/vms/applicationset.yaml), then click **Create**.
2. Open the GitOps instance and watch applications **live-linux-prod-aro** and **live-windows-vdi-aro** reach **Synced / Healthy**. Sync is automatic; no separate Sync click is required.
3. Open **Virtualization → VirtualMachines**. Show **linux-vms-prod / linux-gitops-01** and **windows-vms-vdi / win11-gitops-01**. Linux's Route serves the demo page and `/ready.json`; Windows contains VS Code, guest tools and the Team X desktop/workspace from the golden image.
4. Log in using the cluster Secrets below. For Windows, open **Team X - VS Code** on the desktop and inspect `C:\TeamX\workspace` and `C:\TeamX\image.json`.

| VM | Username | Secret in the VM's project | Password key |
|---|---|---|---|
| `linux-gitops-01` | `fedora` | `linux-vm-login` | `fedora` |
| `win11-gitops-01` | `demo` | `win11-gitops-01-answer` | `password` |

The one-time prerequisites are already installed on this lab. Namespaces, credentials, the AppProject and destination permissions remain ready; the ApplicationSet and its test applications/VMs are removed after rehearsal. The existing presenter VM `win11-dev-01` is independent and remains available.

## CLI equivalent

```bash
oc apply -f https://raw.githubusercontent.com/rh-aelgendy/multi-cloud-virt/main/applicationsets/vms/applicationset.yaml
```

Use the ARO context. To reset after a presentation, delete **only** ApplicationSet `openshift-gitops/live-vms-aro`, with cascading deletion. Application finalizers remove its generated applications and managed VM/Service/Route resources; KubeVirt/CDI remove the two VM clone disks. The source golden images, login Secrets, namespaces, AppProject and existing presenter VM remain.

```bash
oc -n openshift-gitops delete applicationset live-vms-aro --cascade=foreground
```

## Use a later successful pipeline image

Read result **golden-image** from the successful PipelineRun and verify its DataSource is Ready. Before deploying a fresh environment, change `spec.dataVolumeTemplates[0].spec.sourceRef.name` and `metadata.labels.image-version` in `kustomize/windows-vdi/vm.yaml`, then commit and push. The ApplicationSet reads `main`. Changing a source reference does not replace an existing VM's boot disk; reset this demo deployment before provisioning fresh clones from a different image.

## Recreate prerequisites on the same lab

```bash
python3 scripts/prepare-live-vms.py --context ARO_CONTEXT
```

The helper checks the completed Windows pipeline result and Ready DataSource before preparing permissions. It reuses the existing durable ARO GitOps credential, expands only its namespace allowlist, preserves existing login Secrets and logs no passwords or tokens. It does not create an ApplicationSet or VM. The namespace roles permit management only in the two demo projects; the AppProject permits only VM, Service and Route manifests. ROSA is unchanged.

## Rehearsal results — 14 October 2026

Both generated applications reached **Synced / Healthy**, and both VMs reached **Running / Ready** on ARO virtualization nodes. Linux reported `AccessCredentialsSynchronized=True`, its TLS-verified HTTPS `/ready.json` returned 200 with hostname `linux-prod-azure`, and GitOps automatically restored a deliberately changed ownership label. Windows reported Windows 11 through the guest agent and completed unattended setup to the normal lock screen.

Deleting the ApplicationSet with foreground cascading deletion removed both applications, both test VMs, their clone DataVolumes/PVCs, and the Linux Service/Route. The Linux project was checked empty of those workload resources. The existing `win11-dev-01` presenter VM stayed Running/Ready, all four original cross-cloud GitOps applications stayed Synced/Healthy, and the image sources and login Secrets were retained. The prerequisite helper was rerun successfully and preserved both login Secrets.
