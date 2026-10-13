# Team X Windows 11 Developer Desktop — ARO only

A small image-customization demo based on the KubeVirt [windows-customize pipeline](https://artifacthub.io/packages/tekton-pipeline/kubevirt-tekton-pipelines/windows-customize) and its [v0.26.0 source](https://github.com/kubevirt/kubevirt-tekton-tasks/tree/v0.26.0/release/pipelines/windows-customize).

The customization starts from a generalized **Windows 11 Pro** image. It clones that disk, boots a temporary builder VM into Audit mode, installs the team software, captures guest validation, runs Sysprep and publishes a new local boot source. Both pipelines and all builder/runtime VMs run only on ARO; VM and task placement selects `workload=virt`. Images stay on persistent ANF PVCs. This example does not copy anything to ROSA.

```mermaid
flowchart LR
  B[Generalized Windows 11 base] --> C[Clone disk]
  C --> V[ARO builder VM]
  V --> A[VS Code + team workspace]
  A --> T[Guest checks + Sysprep]
  T --> G[Local developer golden image]
  G --> D[New developer desktop VM]
```

## What is visibly different

- Microsoft VS Code **1.141.1**, installed under `Program Files` for all users. Its official system installer URL and SHA-256 are pinned in `software.json`; the guest verifies the checksum and Microsoft Authenticode signature before installation.
- VirtIO guest tools and QEMU guest agent. The one-time base pipeline installs them; the customization validates the agent and retains the tools in the new image.
- Public desktop shortcut **Team X - VS Code**, opening `C:\TeamX\workspace`.
- Public desktop folder **Team X Developer Desktop**, containing a Welcome page showing the platform, image version and included software.
- A sample `README.md` and `hello.ps1` project, plus `C:\TeamX\image.json` with the build version and software version.

The six customization stages are **check-base-and-prepare → clone-base-disk → create-builder → validate-guest-customization → wait-for-sysprep-shutdown → publish-local-golden-image**.

The guest validates Windows 11, guest tools/agent, VS Code system installation/version and CLI execution, the sample project and desktop shortcuts. Publication requires matching captured evidence, observed shutdown and a detached disk. A failed customization leaves the builder running for inspection and cannot publish a successful image.

## One-time base build

ARO's built-in `win11` catalog entry initially had no PVC. `windows11-base-image` creates a real generalized Windows 11 base first. It uses Secure Boot, persistent EFI/TPM, four vCPUs (two sockets with two cores each), 8 GiB RAM, and the installed `windows.11.virtio` preference.

1. Open ARO Console → Pipelines, project **image-factory**.
2. Use the **Windows 11 base image — ARO** PipelineRun YAML sample, or import `base-run.example.yaml`.
3. Supply the Windows 11 ISO HTTPS URL, edition, fresh build/output names, and explicitly set `accept-eula: 'true'` only after accepting the applicable terms.
4. Retain the `image-builder` service account, `workload=virt` task placement and the UID/GID 107 override for the ISO modification task.

The ISO is imported into a persistent DataVolume. Later base builds can reuse it by setting `iso-dv-name` to that existing name and leaving `iso-url` empty. If the earlier ISO modification task succeeded, also set `iso-already-prepared: 'true'`: the vendor modification is a one-time operation and cannot process its own output again. Supplying a different URL with an existing media name fails rather than replacing the media. The current setup imported `win11-base-build1-iso`; the signed download link stays outside Git. The media/PVCs have no scheduled cleanup.

Public samples default to **license acceptance false**. No product activation is performed by these scripts. Use fresh build IDs and output image names for each golden image; existing outputs are never replaced.

## Main audience example: customize the developer desktop

1. In ARO Console, project **image-factory**, select pipeline **windows11-developer-customize**.
2. Import `customize-run.example.yaml` or select **Team X Windows 11 Developer Desktop — ARO** from the Console YAML samples.
3. Set `source-image` to the ready generalized base, normally `win11-base-v1-0-0`.
4. Choose fresh `build-id`, `image-name`, and `image-version` values. The Console customization sample uses `win11-dev-build2`, `win11-dev-v1-1-0`, and `v1.1.0` for a follow-on run.
5. Accept the applicable Windows terms, retain `image-builder` and `workload=virt`, then create the PipelineRun.
6. Open a completed run to show validation evidence and the published boot source while the new run works. A complete installation/customization is longer than a short presentation segment.

The initial target names are **win11-base-v1-0-0** and **win11-dev-v1-0-0**, both in `image-factory`. Captured validation is stored in ConfigMap `<image-name>-evidence`. Golden disks and boot sources persist independently of PipelineRuns; the vendored tasks use `allowReplace: false` and no PipelineRun owner references for those disks.

The VS Code settings are ordinary declarative customization inputs in `windows11-dev-source`. To change software, edit the versioned source and reinstall this package before launching a fresh customization run. Changing that ConfigMap does not alter an already-published golden disk.

## Show a VM created from the result

The ready-to-import VM manifest is `clone.example.yaml`: **windows-vms-vdi / win11-dev-01**, hostname **WIN11-DEV-01**. It clones the developer DataSource, uses Windows 11 Secure Boot/TPM hardware, selects only `workload=virt` nodes and reports guest-agent readiness.

Prepare its unique local login Secret and source-clone permission first:

```bash
python3 scripts/create-windows11-login.py --context ARO_CONTEXT --generate
oc --context ARO_CONTEXT apply -f examples/windows-vms-vdi/clone-permissions.aro.yaml
oc --context ARO_CONTEXT apply -f pipelines/windows11/clone.example.yaml
```

The project `windows-vms-vdi` already exists from the compliance demo. On a fresh setup, create it using `examples/windows-vms-vdi/namespace.yaml` first. The default username is **demo**; reveal the password from Secret **win11-dev-01-answer**, key **password**, in that project. No password or token is written to Git or logged by the helper. Existing login Secrets are preserved. The runtime answer file creates a local account and does not use automatic password-bearing logon.

Open the VM's Console/VNC tab, log in, and show the public desktop folder and VS Code shortcut. Open `hello.ps1` and the README in VS Code. Show the same software/workspace on another clone using unique VM, disk, hostname and Secret names. Keep sealed builder VMs halted; create clones from the DataSource rather than starting the golden source disk.

Suggested narration: **“The pipeline turns a clean Windows desktop into our team's standard developer environment. Every VM starts with the same tools and workspace, without repeating the install by hand.”**

## Install and validate

```bash
oc --context ARO_CONTEXT apply -k pipelines/windows11
oc --context ARO_CONTEXT apply -f console/windows11-samples.yaml
bash scripts/validate.sh
```

This package reuses the existing `image-factory/image-builder` account, its namespace role and the reviewed `modify-windows-iso-file` task/SCC from the earlier demo. It vendors the upstream `modify-data-object`, `create-vm-from-manifest` and `wait-for-vmi-status` tasks at v0.26.0, with their AMD64 image pinned by digest. Their original license is in `tasks/LICENSE`. No runtime Hub resolver or remote mutable ConfigMap import is used. `image-controller.py` adds preparation, guest evidence validation and safe local publication around the upstream task flow.

Live run results will be added after Windows execution and first-boot verification complete.

If a builder displays a PowerShell error, publication remains blocked. The script copies its startup-resume script from the answer CD; cleanup uses `Remove-Item -Force` because that copy can retain the CD's read-only attribute. Build `windows11-base-image-fw2ms` exposed this issue and was cancelled before publication. Restarting an interrupted Windows Setup did not resume successfully, so the corrected build uses a fresh disk and reuses the already imported ISO. Do not use the failed builder disk as a golden image.

References: [KubeVirt Windows customization source](https://github.com/kubevirt/kubevirt-tekton-tasks/tree/v0.26.0/release/pipelines/windows-customize), [Microsoft VS Code system setup](https://code.visualstudio.com/docs/setup/windows#_install-with-the-system-setup).
