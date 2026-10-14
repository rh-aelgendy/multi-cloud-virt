# Guest login credentials in the Console

The installed virtualization console (release 4.21) reads the first cloud-init volume's inline `user` and `password` fields. It does not resolve our guest-agent login Secrets or Windows Sysprep Secrets for this panel.

The opt-in lab helper `scripts/enable-console-logins.py --apply` copies existing credentials from named login Secrets into the live VM resources. It never writes passwords to Git or local files, never rotates credentials and never restarts a VM. Default invocation only lists the targets and reads no Secrets. Absent live-demo VMs are skipped; rerun after deploying them.

**This broadens access to plaintext credentials:** anyone who can read these VM resources can read their passwords. Secrets remain the original source; the VM contains an additional display copy. Use this only when intentionally accepted for the lab. Do not export these live VM objects to a public repository.

For Linux the helper preserves the existing cloud-init application script and adds the matching account/password with password expiry disabled. For Windows it adds an unmounted `console-login-display` cloud-init volume that the console reads, or reuses an existing credential-only `cloudinitdisk`; Windows authentication continues to use the existing Sysprep-created account. This volume is a console display adapter, not a Windows guest configuration mechanism. No disk is attached to the running guest. Template changes may show a pending restart indication, but viewing/copying credentials needs no restart.

ApplicationSets ignore only the named runtime console-display volume (including the existing Windows `cloudinitdisk` and its matching disk definition where present) and the Linux cloud-init userData string, scoped to the individual demo VM names and namespaces, with `RespectIgnoreDifferences=true`, so self-healing does not remove these runtime-only passwords. Because cloud-init userData is one string, this also ignores later changes to its application bootstrap script for these demo Applications. To roll out a changed bootstrap script, remove the exception deliberately and re-run the display helper afterwards; normal VM CPU/memory/disk GitOps remains managed.

Open the VM → **Console** → **Guest login credentials**, reveal/copy the username and password, then use the console's paste action to enter them. Refresh the page if it was already open.

Implementation reference: [release-4.21 credential reader](https://github.com/kubevirt-ui/kubevirt-plugin/blob/release-4.21/src/utils/resources/vmi/utils/cloud-init.ts).

Validated on 2026-10-14: seven running lab VMs across ARO and ROSA have parseable username/password fields matching their existing Secrets. All four existing Argo Applications remain Synced/Healthy, and all guests remain Running/Ready. The stopped image-builder VM was excluded. The two removed live-demo VMs were skipped and remain absent.

Applying an unmodified fixture manifest directly can overwrite the runtime inline display fields; rerun the helper afterwards. Secret rotation also requires rerunning the helper to refresh the display copy.
