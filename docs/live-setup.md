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

The empty `linux-vms-prod` and `windows-vms-vdi` projects now exist on both destinations for these scenarios and future standalone examples. No example workload was deployed into them. See [the compliance presenter guide](../governance/compliance-demo/README.md) for UI steps, expected results and reset commands.
