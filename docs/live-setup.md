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

## Pending Windows input

The user will supply the Windows ISO and accept the license in the ARO UI. No Windows image has been built, no Windows guest test has passed, and no Windows runtime VM is running yet. The ready PipelineRun sample defaults to `accept-eula: false`.

GitOps applications initially use manual sync. After the image pipeline publishes the ARO source and stages the ROSA source, Sync both applications and validate first boot, QEMU agent, IIS version/cloud identity and restart readiness. Enable self-healing after that rehearsal.

ROSA is a hypothetical DR destination: image availability and consistent VM provisioning are demonstrated, not application-data replication or automatic failover.
