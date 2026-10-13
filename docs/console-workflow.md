# Show and tell from ACM and the ARO console

## Before the audience arrives

Open the ARO web console, its GitOps/Argo CD console, and ACM. ARO hosts all pipeline tasks and the image-builder VM; ROSA HCP is the imported hypothetical DR destination.

Build and test Windows **before** the 15-minute presentation. A complete installation/Sysprep/image copy cannot reliably finish in that time. Keep a completed run and both ready VMs to show. When starting another run live, clearly distinguish it from the completed run.

## Build through ARO UI

1. Select project **image-factory** and open **Pipelines**. Inspect `team-x-platform-readiness` and its successful check.
2. Open `team-x-windows-golden-image` and show its five stages.
3. Create a PipelineRun using the console's YAML editor. Select the **Team X Windows Golden Image — ARO** sample if available, or paste `pipelines/run.example.yaml` from the repository.
4. Supply an approved Windows Server 2022 English x64 ISO URL; explicitly set `accept-eula` to `"true"` after accepting its terms. Choose a unique `build-id` and image version. Leave the configured ARO/ROSA storage classes and pinned toolbox/VirtIO references intact.
5. Keep `taskRunTemplate.serviceAccountName=image-builder`, the `workload=virt` nodeSelector, the ISO task's UID/GID 107 override, workspace and timeouts. A simple Start form that drops those settings is insufficient; use the complete YAML sample.
6. Create the run and inspect its graph and logs. In ARO Virtualization, locate the temporary builder VM and confirm its node is one of the `workload=virt` workers.
7. When the run succeeds, inspect the local `team-x-windows-v1-0-0` DataSource in ARO `image-factory`, and the same DataSource in ROSA `team-x-images`. The golden disks remain local to their respective clusters.

A failed validation or Sysprep step must be investigated before release. A successful readiness run is not a completed Windows build.

## Release through ARO GitOps UI

Open applications `team-x-windows-aro` and `team-x-windows-rosa`. They initially require manual Sync because no Windows golden image is present until you build it. After the two local DataSources are ready, Sync both applications and watch VM creation and local disk clones.

Check each VM's guest-agent state and `/ready.json` endpoint, then open its Route. Both IIS pages must display Team X and the same golden-image version, with different cloud names and hostnames. For VNC login, reveal the unique Administrator password from that cluster's `team-x-win-v100-answer` Secret; do not display it to the audience.

For drift repair, enable automatic sync/self-healing in the ApplicationSet's Git definition after image validation. Remove only the ROSA VM's live `metadata.labels.owner` through Argo's resource edit action if permitted. Otherwise open the ROSA console from ACM and edit that VM's YAML. Watch ARO GitOps restore the label. Do not edit the desired label in Git for this demonstration.

## Manage through ACM

In ACM fleet virtualization, find both Windows VMs and show cluster placement. Inspect or restart through a supported VM action, then verify guest/application readiness. Use the Team X policy as the common standard. GitOps may repair drift before ACM reports it, so do not promise a transient governance alert.

ROSA is a hypothetical DR destination with a staged image and an independent VM. This workflow does not replicate application data or implement automatic failover. Say that explicitly when using the DR framing.

## Several days later

Prepared GitOps credentials and VM Secrets do not have a 24-hour deadline. The image sources are persistent PVCs. Before the presentation, check clusters/nodes, storage, GitOps connectivity, ACM availability and Windows readiness. Use a fresh ISO link only if starting another build; existing VMs do not need the original ISO URL.
