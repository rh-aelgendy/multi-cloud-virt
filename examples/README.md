# Standalone demos with clear project names

These examples do not rename or move the existing `team-x` workloads. They provision independent VMs in the projects below. Both cloud overlays retain the required ARO `workload=virt` and ROSA metal placement.

| Project | VM | Bootable volume | Console login |
|---|---|---|---|
| `linux-vms-prod` | `linux-web-01` | Existing `fedora` DataSource | `fedora`; password in `linux-vm-login`, key `fedora` |
| `windows-vms-vdi` | `win-vdi-01` | Built `team-x-windows-v1-0-0` DataSource | `Administrator`; password chosen when creating `win-vdi-01-answer` |

`linux-vms-prod` is a naming example for this lab; its VM manifest is not a production-hardening baseline.

## Linux example

Create the project and login Secret on each chosen destination before creating the VM:

```bash
oc --context ARO_CONTEXT apply -f examples/linux-vms-prod/namespace.yaml
python3 scripts/create-linux-login-secret.py --context ARO_CONTEXT --namespace linux-vms-prod
oc --context ARO_CONTEXT apply -f examples/linux-vms-prod/clone-permissions.aro.yaml
oc --context ARO_CONTEXT apply -k examples/linux-vms-prod/aro
```

For ROSA, use `ROSA_CONTEXT` and the `rosa` paths. Omit `--generate` to enter a password you choose; add it to generate a unique password held only in the cluster Secret. Existing Secrets are preserved.

KubeVirt applies the password through the guest agent. Wait for `AgentConnected` and `AccessCredentialsSynchronized` on the VM instance, then log in as `fedora` through Console/VNC. The username is the Fedora boot source's default account; cloud-init creates it. No password is stored in Git, and no external SSH Service is exposed.

The application Route is `linux-web`. Its page shows the destination cloud and hostname.

## Windows VDI example

First complete the Windows image pipeline so the local golden DataSource is ready on the destination. Create a separate answer Secret with the namespace and hostname you want:

```bash
python3 scripts/create-runtime-secret.py --context ARO_CONTEXT --namespace windows-vms-vdi \
  --cloud azure --hostname VDI-AZ-01 --version v1.0.0 --secret-name win-vdi-01-answer
oc --context ARO_CONTEXT apply -f examples/windows-vms-vdi/clone-permissions.aro.yaml
oc --context ARO_CONTEXT apply -k examples/windows-vms-vdi/aro
```

For ROSA, use `ROSA_CONTEXT`, `--cloud aws`, `--hostname VDI-AWS-01` and the `rosa` paths. The helper prompts for the Administrator password, writes it directly into the answer Secret (key `password`), and does not log it or save it locally. Each clone gets its own hostname/password; changing an answer Secret after specialization does not reset an existing Windows password.

The application Route is `windows-vdi-web`.

## Use the console or GitOps

The four files in `examples/rendered/` are complete, rendered Namespace/VM/Service/Route YAML bundles ready for the Console's Import YAML view. Prepare the referenced Secrets and source-clone permissions first. The Secret helper output tells you which Secret/key contains the login password; reveal it only when needed.

You can point a GitOps application at any of the four Kustomize directories. Authorize the destination service account for the chosen project and source-clone namespace, add that namespace to the registered cluster's namespace list and AppProject destinations, then create the application. The existing demo registration is intentionally limited to `team-x`; these future projects are not silently granted access or deployed by setup.

Updating VM `accessCredentials` for an already-running VM can require a restart to mount the credential Secret. The guest agent then propagates the password, and later Secret changes can update it without putting credentials in Git.
