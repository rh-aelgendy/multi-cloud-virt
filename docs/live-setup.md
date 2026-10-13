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
- Local YAML/Kustomize, wiring/placement and nine controller/answer-file checks passed.

## Declarative VMs from existing bootable volumes

Both `team-x-linux` VMs are running from their clusters’ existing Fedora DataSources. ARO placement is `workload=virt`; ROSA placement is the metal worker. Both GitOps applications are Synced/Healthy, guest agents connected, and HTTPS `/ready.json` returns HTTP 200 with distinct cloud/hostname values. A harmless ownership-label drift on ROSA was automatically repaired to `owner=team-x`.

The GitOps instance uses strict RBAC handling and a resource-type inclusion list scoped to the two demo clusters. Its cache issue was resolved without granting the destination accounts cluster-admin.

The earlier disposable transfer probe was cancelled and its image/export resources removed.

## Windows build in progress

The user supplied the Microsoft Windows Server 2022 ISO URL and explicitly accepted its evaluation terms. PipelineRun `team-x-image-xnrwn` is running. ISO import and media preparation succeeded. Windows Server 2022 Datacenter Evaluation is installed with its guest agent connected; the pipeline captured successful VirtIO, guest-agent, IIS and HTTP validation. Generalization, image staging and runtime first boot are still being completed. The reusable UI sample still defaults to `accept-eula: false` for future runs.

GitOps applications initially use manual sync. After the image pipeline publishes the ARO source and stages the ROSA source, Sync both applications and validate first boot, QEMU agent, IIS version/cloud identity and restart readiness. Enable self-healing after that rehearsal.

ROSA is a hypothetical DR destination: image availability and consistent VM provisioning are demonstrated, not application-data replication or automatic failover.
