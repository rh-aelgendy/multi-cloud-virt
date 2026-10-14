# Live setup record — 13 October 2026

## Completed

- Confirmed ARO 4.21.22 and Virtualization 4.21.17, with HCO's existing placement `workload=virt` and three labeled virtualization workers.
- Confirmed ACM manages `acm-hub-aro` and `rosa-virt-dr`, both available and in the default cluster set.
- Confirmed ROSA HCP has an `m5zn.metal` KVM-capable worker and FSx ONTAP-backed `trident-csi` RWX/Filesystem storage; ARO uses `anf`.
- Installed the Windows golden-image and platform-readiness pipelines, controller scripts and reviewed Red Hat ISO task on ARO.
- Built the toolbox image on ARO; its digest is pinned in the PipelineRun sample.
- Read-only platform readiness succeeded on an ARO `workload=virt` node: toolbox execution, XML parsing, image RBAC and ACM transfer RBAC passed.
- Vendor ISO tools succeeded under UID/GID 107 and the custom restricted SCC. KVM was readable/writable; guestfish, qemu-img and xorriso ran. No Windows ISO or license acceptance was involved.
- Registered both GitOps destinations with namespace-scoped, TLS-verified credentials valid until revoked. Earlier 24-hour credentials have been replaced in Argo's cluster Secrets.
- Created distinct Windows runtime Secrets on both destinations. Passwords are held only in Kubernetes Secrets.
- Installed the Team X Windows Golden Image Console YAML sample.
- Installed ACM inform-only ownership/version policy and confirmed placement selects exactly the two demo clusters.
- Local YAML/Kustomize, wiring/placement and ten controller/answer-file checks passed.

## Declarative VMs from existing bootable volumes

Both `team-x-linux` VMs are running from their clusters’ existing Fedora DataSources. ARO placement is `workload=virt`; ROSA placement is the metal worker. Both GitOps applications are Synced/Healthy, guest agents connected, and HTTPS `/ready.json` returns HTTP 200 with distinct cloud/hostname values. A harmless ownership-label drift on ROSA was automatically repaired to `owner=team-x`.

The GitOps instance uses strict RBAC handling and a resource-type inclusion list scoped to the two demo clusters. Its cache issue was resolved without granting the destination accounts cluster-admin.

Both Linux VMs were restarted after adding Secret-backed guest-agent password propagation. Both report `AccessCredentialsSynchronized=True`, and their HTTPS readiness checks still return HTTP 200. Log in as `fedora` using the password from the local `team-x/linux-vm-login` Secret, key `fedora`.

The earlier disposable transfer probe was cancelled and its image/export resources removed.

## Windows image and runtime validation

The user supplied the Microsoft Windows Server 2022 ISO URL and explicitly accepted its evaluation terms. Run `team-x-image-xnrwn` successfully imported/prepared the ISO, installed Windows Server 2022 Datacenter Evaluation, captured VirtIO/guest-agent/IIS/HTTP validation, observed Sysprep shutdown and published the ARO golden DataSource. ACM's CDI copy then succeeded on ROSA.

The original run was cancelled after the copy because its feedback parser used incorrect field names. The parser now reads ACM's actual `statusFeedback.values[].fieldValue.string`, with a regression check. Completion PipelineRun `team-x-image-complete-mrm82` succeeded, verified the real `Succeeded` feedback, retained both golden disks and removed the export and transfer Secrets. Do not describe the original run as entirely green; inspect its successful build tasks and the separate green completion run in the UI.

Both clusters have ready local DataSource `team-x-windows-v1-0-0` (ARO `image-factory`; ROSA `team-x-images`). Both Windows applications are Synced/Healthy. Their HTTPS `/ready.json` endpoints return HTTP 200, version `v1.0.0`, and the correct identities: Azure `TEAMX-AZ-01`, AWS `TEAMX-AWS-01`. Both guest agents connected and console screenshots showed normal Windows lock screens, with no OOBE prompts. Restart readiness passed on both ARO and ROSA, with all four applications returning Synced/Healthy and all four HTTPS readiness endpoints returning HTTP 200.

Integration corrections are retained in source: ROSA's importer limit was raised from `600M` to `2Gi` through the HCO storage settings; runtime scripts are on the Secret-backed CD to respect Windows' 259-character command limit; locale/account settings complete unattended OOBE. The unused ARO runtime clone was recreated while correcting those settings. The sealed golden disk was preserved.

The reusable UI sample still defaults to `accept-eula: false`. Fresh builds require a new build ID and image version. The Windows applications use manual sync; the Linux applications provide the verified automated self-healing demonstration.

ROSA is a hypothetical DR destination: image availability and consistent VM provisioning are demonstrated, not application-data replication or automatic failover.

## ACM one-action compliance scenarios

Three additional policies in `vm-demo-policies` were installed, rehearsed and reset: `demo-01-project-ownership`, `demo-02-vm-capacity` and `demo-03-golden-image-catalog`. Each reached Compliant on both clusters in Enforce mode, then returned to Inform/NonCompliant on both clusters. Project/catalog label changes and quota specifications were checked directly. Both clusters admitted two halted diskless VM definitions and rejected a third through the VM object-count quota; all probes were removed. Existing four GitOps applications remained Synced/Healthy.

The `linux-vms-prod` and `windows-vms-vdi` projects exist on both destinations. The Linux projects remain empty for the optional quota admission test. ARO `windows-vms-vdi` now contains the Windows 11 presenter VM described below; the two-VM quota leaves one additional VM slot there. See [the compliance presenter guide](../governance/compliance-demo/README.md) for UI steps, expected results and reset commands.


## Windows 11 developer image — 14 October 2026

ARO-only customization PipelineRun `windows11-developer-customize-j6wd8` succeeded end to end in **12 minutes 9 seconds**, with **8 tasks passed, 0 failed, 0 cancelled and 0 skipped**. It uses upstream v0.26.0 tasks to clone the base disk, create the builder, wait for VMI `Succeeded`, create the Ready DataSource and clean up the temporary VM in `finally`. A second `finally` task removes only the per-build answer ConfigMap and validation Service. The golden root disk, DataSource and evidence remain independent of PipelineRun ownership. No Windows 11 resources were deployed to ROSA.

Guest evidence in `image-factory/win11-dev-v1-1-0-evidence` confirms Windows 11 Pro, VirtIO tools, QEMU guest agent, Microsoft VS Code **1.141.1** system installation and CLI execution, the Team X sample workspace and public desktop shortcuts. Local DataSource `image-factory/win11-dev-v1-1-0` is Ready. The earlier full customization run `windows11-developer-customize-pnnhn` also succeeded and produced `win11-dev-v1-0-0`.

Presenter VM `windows-vms-vdi/win11-dev-01` cloned the v1.1.0 image and reached Running/Ready with the guest agent connected. Its first boot completed to the normal Windows lock screen, without OOBE prompts. Log in as `demo`; the unique password remains only in that project's `win11-dev-01-answer` Secret, key `password`. The manifest uses `workload=virt`, persistent Windows 11 EFI/TPM hardware and the local ANF boot source. See [the Windows 11 presenter guide](../pipelines/windows11/README.md).

The initial Windows cleanup failure came from deleting a read-only copy of the CD script; cleanup now uses `Remove-Item -Force`. A later publication failure came from requiring the completed VMI to still exist after the native shutdown wait had succeeded. The final pipeline follows upstream publication and explicit finally cleanup, avoiding that redundant lookup. The completed builder and input resources were checked absent; its root disk and Ready DataSource were checked present. Existing four GitOps applications remain Synced/Healthy, and the three audience compliance policies remain Inform/NonCompliant.

Fresh base PipelineRun `windows11-base-image-cz7dz` completed with five passed tasks and zero failures; ISO modification was intentionally skipped because the imported ISO had already been prepared. It published Ready base `win11-base-v1-1-0`. This run retained its pre-transition pipeline snapshot; its builder and temporary inputs were subsequently removed with the upstream cleanup task. New base runs use the explicit finally cleanup definition. The temporary publication helper and its TaskRun-read RBAC were removed after all earlier runs completed. Future customization samples select the fully verified v1.1.0 base.

## Live GitOps ApplicationSet rehearsal — 14 October 2026

`applicationsets/vms/applicationset.yaml` generates `live-linux-prod-aro` and `live-windows-vdi-aro`, following the user's list-generator/Kustomize reference. Both applications reached Synced/Healthy, with `linux-vms-prod/linux-gitops-01` and `windows-vms-vdi/win11-gitops-01` Running/Ready on `workload=virt` nodes. Windows cloned pipeline output `win11-dev-v1-1-0` and completed to the normal lock screen. Linux password propagation reported synchronized, its TLS-verified HTTPS readiness endpoint returned 200, and automatic self-healing restored an ownership-label drift.

The ApplicationSet was then deleted with foreground cascading deletion. Both generated applications and test VMs, their clone disks, and the Linux Service/Route were checked absent. Existing `win11-dev-01` and the four original cross-cloud GitOps applications stayed healthy. The AppProject, namespace roles, source-clone permission and unique login Secrets remain prepared. The existing durable ARO GitOps registration now additionally permits `linux-vms-prod` and `windows-vms-vdi`; its credential/configuration was preserved, with no new expiring token. ROSA was unchanged. See [the live deployment steps](../applicationsets/vms/README.md).

## VM fleet observability and right-sizing — 2026-10-14

Installed demo-owned ACM MultiClusterObservability on ARO with a private Azure Blob backend, `managed-csi` Thanos PVCs, MCOA platform collection, Perses console integration, namespace analytics and native virtualization right-sizing analytics. All MCO components are Ready; both `acm-hub-aro` and `rosa-virt-dr` add-ons are Available. The storage account disables anonymous Blob access; credentials remain in Kubernetes Secrets with no SAS expiry. Private storage resource details are recorded only in ignored `.local/demo/vm-observability-storage.json`.

Created dedicated `linux-vms-prod/linux-oversized-aro` and `linux-vms-prod/linux-oversized-rosa` fixtures at 8 vCPU / 16 GiB each. ARO uses `workload=virt`; ROSA uses m5zn.metal. Both are Running/Ready, guest agents connected, login credentials synchronized. Rehearsed stop → 2 vCPU / 2 GiB → Running/Ready on both, then restored oversized opening sizes. TLS Routes `/ready.json` returned HTTP 200 and correct cloud/hostname on both clusters. Existing Windows and live GitOps examples were retained separately.

Custom dashboard **VM Fleet — Right-sizing opportunities**, project `open-cluster-management-observability`, has Available=True and Degraded=False. All ten PromQL queries passed against central Thanos. `scripts/verify-vm-observability.py --require-candidates` passed with both fixtures flagged: ARO approximately 0.28% CPU / 3.15% guest memory (24 real samples), ROSA approximately 0.21% CPU / 3.15% guest memory (21 real samples). Candidate criteria are explicitly a demo heuristic: observed 15-minute CPU peak <20%, guest memory peak <40%, at least 20 actual memory samples. Missing metrics are never filled with zero. Fleet vCPU count uses distinct per-vCPU IDs because ROSA lacks the ARO convenience `kubevirt_vmi_vcpu_count` metric. Restarted only the newly installed ROSA collector to load its generated updated scrape config.

ACM-managed **ACM Right-Sizing OpenShift Virtualization VM Overestimation**, project `observability-analytics`, is installed and reconciled. Native VM recording rules are installed on both clusters; their historical recommendation group evaluates every 15 minutes. At the custom-dashboard verification checkpoint, native per-VM recommendation series had not yet been generated. No history was fabricated or native evaluations forced. Leave collection running overnight; the presenter guide distinguishes native recommendations from the custom candidate heuristic and illustrative 2-vCPU/2-GiB change. No cloud billing reduction is claimed.

Presenter steps and reproducible setup: [observability/README.md](../observability/README.md).
