# Deployment and lifecycle

## Topology and prerequisites

ARO is the fixed build and management hub, with Pipelines, GitOps, ACM and Virtualization already installed. ROSA HCP is imported as `rosa-virt-dr` and supplies an Intel bare-metal virtualization worker. The two clusters belong to ACM's `default` cluster set.

The factory and ARO VM explicitly select `workload=virt`, matching HCO placement. The ROSA VM selects `node.kubernetes.io/instance-type=m5zn.metal`. Neither operator installation nor HCO placement alone substitutes for these workload selectors. HCO is not modified by this demo setup.

ARO uses `anf`; ROSA uses `trident-csi`. Both have RWX Filesystem support. Temporary and final images stay on PVCs. CDI/Trident may also allocate transient scratch/snapshot volumes. Leave capacity for a 64Gi ARO root disk, 9Gi ISO, 1Gi pipeline workspace, an 80Gi ROSA golden disk and an 80Gi runtime disk on each cloud; ANF minimum-volume sizes and scratch allocations can exceed those nominal requests. The ANF pool's allocation/throughput budget must include these volumes.

The builder requests 4 vCPU/8Gi; runtime VMs request 2 vCPU/6Gi. The ISO task also requests KVM and has two 12Gi ephemeral scratch volumes. ARO workload nodes have virtualization support; ROSA placement excludes ordinary m5.xlarge nodes.

## Installed resources

`pipelines/kustomization.yaml` installs the namespaced factory resources. `pipelines/dr-rbac.yaml` separately allows `image-factory/image-builder` to create/update/read ManifestWorks only in `rosa-virt-dr`. The reviewed vendor ISO task is vendored at version 4.21.0, so execution does not depend on a live hub catalog lookup.

`pipelines/iso-scc.yaml` is the explicitly approved custom SCC: UID/GID 107 only, no privileged containers, no host network/PID/IPC/paths, dropped capabilities and RuntimeDefault seccomp. Only the dedicated image-builder service account can use it. No broad `anyuid` grant is used.

The toolbox is built inside ARO from `tools/aro-build.yaml` and stored in its integrated registry. The Windows PipelineRun template pins the successfully built image digest. It needs no local container engine or Git clone to bootstrap because the BuildConfig embeds the Containerfile.

## Credentials and lab duration

The user requested a lab that can be shown several days later. GitOps uses Kubernetes service-account token Secrets bound to `team-x/team-x-gitops` in each destination. They have no fixed 24-hour expiry; deleting their Secrets or service accounts revokes access. Permissions are limited to the `team-x` namespace, plus the right to clone from the appropriate demo image namespace. Tokens are held only in cluster Secrets, never in Git or logs. TLS verification stays enabled.

`gitops/runtime-rbac.yaml` and `gitops/clone-rbac.yaml` document those permissions. `scripts/register-gitops.py` can re-register them after revocation, with explicit context arguments. It is not necessary to rerun registration before an ordinary presentation in 2–3 days.

`scripts/create-demo-runtime-secrets.py` generates unique passwords directly into each cluster's `team-x-win-v100-answer` Secret. It preserves existing passwords on repeated runs. Reveal `username` and `password` through the Console Secret view only when needed. The unattended answer also lives in that Secret. No automatic administrator logon, public RDP service or password in the golden image is configured.

The ISO URL is supplied when a Windows run is launched. Temporary signed download links can expire independently; use a fresh URL or a durable approved ISO mirror at build time. Licensing/evaluation duration is governed by the ISO and terms you choose. This is separate from the lab's GitOps credentials and retained storage.

## Factory pipeline

Use `pipelines/run.example.yaml` or the ARO console's **Team X Windows Golden Image — ARO** YAML sample. Preserve its service account, nodeSelector, task security settings, workspace and timeouts. Fill in the ISO and set `accept-eula` to `"true"` only after accepting the applicable terms. Use a fresh build ID and semantic image version for each new build.

1. **prepare** — refuses unaccepted terms; creates per-run answer media, root disk and ISO import; waits for the ISO before it can be modified.
2. **modify-windows-iso-file** — reviewed Red Hat task removes the unattended EFI boot prompt, on an ARO virtualization node.
3. **install-and-validate** — installs Windows, VirtIO/QEMU agent and IIS; records guest validation evidence; resumes required installation reboots; generalizes with Sysprep and waits for shutdown.
4. **publish-local-image** — checks the evidence and halted/detached builder, then creates a versioned ARO DataSource and validation ConfigMap. It never overwrites an existing release name.
5. **stage-dr-image** — temporarily exports the ARO golden PVC, creates an ACM ManifestWork with token-authenticated CDI import and a local ROSA DataSource, and waits for import success. It removes the transfer credentials/export once staging completes.

The disk stays on ARO ANF throughout. ROSA receives its own local copy and then clones locally for runtime VMs. Export endpoints have a bounded lifetime during a running build; the resulting local images and VMs do not depend on those endpoints remaining available. A failed transfer leaves the ARO golden image intact; inspect the ManifestWork and CDI events, then retry transfer using a fresh export rather than reusing an expired URL.

The answer targets Windows Server 2022 English x64 and an ISO image description of `Windows Server 2022 SERVERDATACENTER`. Confirm the exact description matches the ISO, and that the intended edition is Desktop Experience. Driver paths assume `2k22`; the initial device layout assumes E: is the VirtIO CD and F: the answer CD. Check those in the first rehearsal. Firmware is EFI with Secure Boot disabled for this minimal demo.

A failing guest script stays powered on for inspection instead of publishing a possibly invalid disk. Use ARO VNC and inspect `C:\TeamX\FAILED.txt`, `build.log` and Sysprep Panther logs. The controller captures an HTTP success marker during the 180-second pre-Sysprep window. If a controller outage misses it, the run fails safely. Once sealed, do not boot the builder again; clone the DataSource to inspect the image.

## GitOps and ACM

The repository is `https://github.com/rh-aelgendy/multi-cloud-virt`. ARO GitOps registers destinations `acm-hub-aro` and `rosa-virt-dr`. The ApplicationSet creates one application per overlay.

Applications start with `automated.enabled: false`. After both DataSources are ready, Sync each application through the ARO GitOps UI. This creates the VM, Service and Route. Then enable automated synchronization/self-healing in the GitOps definition for the drift demonstration; pruning remains disabled and application deletion preserves workloads.

The VM base uses a local DataSource instead of an external image URL. ARO clones from namespace `image-factory`; ROSA clones from `team-x-images`. A runtime Secret is required on each cluster. Windows specialization sets a unique hostname and produces IIS pages containing team, cloud and image version. Guest readiness is checked with `/ready.json`; an Argo Synced status alone does not prove Windows is ready.

The ACM policy selects the two ManagedClusters labeled `demo=vm-islands`, through the default cluster set. It reports ownership/image-version compliance only. Before Windows exists, noncompliance is expected; do not interpret it as a platform fault. GitOps is the sole drift repair owner.

## New versions and cleanup

A new image version requires a fresh build ID, DataSource, VM name, disk name and runtime answer Secret. Keep the previous VM/disk until the new VM is ready, then switch the Service's image-version selector. This is replacement provisioning, not an in-place Windows OS upgrade or application-data recovery.

Cleanup is deliberate: disable/remove GitOps applications with resource preservation first; inspect VM/PVC ownership and reclaim policy before deleting disks. Removing a VM-owned DataVolume may delete backing ANF storage; ROSA's Trident class uses Retain and can leave backing storage requiring explicit cleanup. Remove only the demo's named resources, ManifestWorks, export tokens and workspace PVCs. Deleting a retained image ManifestWork can remove the managed ROSA golden-image resources it owns.

Revoke GitOps credentials by deleting `team-x-gitops-token` on each destination and the corresponding Argo cluster Secret. Remove the approved SCC binding/role/SCC when the image factory is retired. No routine cleanup is scheduled to expire or delete the lab before the presentation.
