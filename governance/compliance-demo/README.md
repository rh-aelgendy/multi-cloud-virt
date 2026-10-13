# One ACM action, two clouds

Three small operating-standard policies are installed in the ARO hub namespace `vm-demo-policies`. The existing `vm-demo` placement selects exactly `acm-hub-aro` and `rosa-virt-dr`. All three are left in **Inform / NonCompliant on both clusters**, ready for the presenter to enforce.

These scenarios demonstrate platform configuration compliance. The golden-image policy checks catalog metadata; it does not inspect guest patches, vulnerabilities or prove regulatory compliance.

| Policy | Before: Inform | After: Enforce | Show the audience |
|---|---|---|---|
| `demo-01-project-ownership` | Ownership/cost-center labels missing from `linux-vms-prod` and `windows-vms-vdi` | Adds `demo.openshift.io/owner=team-x` and `demo.openshift.io/cost-center=virt-demo` to both projects, on both clusters | “Teams inherit the same ownership standard in Azure and AWS.” Open either project YAML and show the two labels. |
| `demo-02-vm-capacity` | `demo-vm-capacity` ResourceQuota missing from both projects | Creates a maximum of **two VirtualMachine objects per project**, on both clusters | “The same capacity guardrail follows the team.” Open ResourceQuotas and show `count/virtualmachines.kubevirt.io: 2`. |
| `demo-03-golden-image-catalog` | Catalog ownership/lifecycle labels missing from the existing Windows golden DataSource | Adds `demo.openshift.io/catalog-owner=team-x` and `demo.openshift.io/lifecycle=golden`; requires `image-version=v1.0.0` | “The image catalog carries the same release metadata across clouds.” Show the DataSource labels on ARO and ROSA. |

The projects already exist. `linux-vms-prod` is empty on both clusters and is the default namespace for the optional quota admission test. ARO `windows-vms-vdi` contains the Windows 11 presenter VM `win11-dev-01`; the two-VM quota leaves room for one additional VM there. The original cross-cloud VMs remain in `team-x`. The catalog policy selects existing namespaces `image-factory` on ARO and `team-x-images` on ROSA; do not create the opposite image namespace on either destination without adjusting the selector. No VM restart is needed for any of these scenarios.

## Presenter steps: about three minutes

1. Open ACM **Governance → Policies**. Select namespace `vm-demo-policies`, and filter names starting with `demo-0`.
2. Open one policy. Show its description, remediation **Inform**, and violations for both `acm-hub-aro` and `rosa-virt-dr`.
3. Use the policy's **Actions → Enforce** action and confirm the dialog. Change the parent Policy, rather than editing the nested ConfigurationPolicy. The parent remediation mode overrides the template mode.
4. Wait for both cluster rows to become **Compliant**. This is asynchronous reconciliation; a single hub action applies the policy to both destinations.
5. Open the affected project, quota or DataSource and show the actual fields from the table above.
6. Repeat with another policy, or select all three and use the bulk Enforce action for the strongest “one operating model” moment.

Recommended sequence: project ownership first (easy visual change), VM quota second (a real admission guardrail), golden catalog last (connects back to the pipeline). Keep the existing Windows/Linux pages open to show that the applications keep running.

For the golden-image policy, open boot source `team-x-windows-v1-0-0`: ARO namespace `image-factory`, ROSA namespace `team-x-images`. Bootable volumes/DataSources are Kubernetes resources; this policy labels the catalog entries and does not block use of other boot sources.

The quota counts VM definitions, including halted VMs, rather than only running instances. It does not delete existing VMs when the quota is lowered. If the project already contains two VMs, the next VM create is rejected with `exceeded quota: demo-vm-capacity`. The limit applies only to the two new example projects, not `team-x` or the image factory.

## Verified results

Rehearsed on **13 October 2026**:

- All three policies: **Inform / NonCompliant on 2 of 2 clusters → Enforce / Compliant on 2 of 2 clusters**.
- Confirmed project labels, VM ResourceQuota hard limits and golden-image labels on both destinations.
- Admission test passed on ARO and ROSA: two temporary halted, diskless VM definitions were accepted; the third server-dry-run request was rejected by the VM count quota. All probe definitions were removed. No VM instance or disk was created.
- Reset returned all three policies to **Inform / NonCompliant on both clusters** for the live demo.

## Reset and rehearsal

Switching a policy back to Inform stops remediation but leaves the applied labels and quotas in place. To restore the visible violations, use the narrowly scoped helper:

```bash
python3 scripts/compliance-demo.py reset --aro-context ARO_CONTEXT --rosa-context ROSA_CONTEXT
```

It first waits until Inform reaches the managed-cluster ConfigurationPolicies, then removes only the four demo metadata keys and the named `demo-vm-capacity` quotas. It preserves projects, VMs, disks, image versions, clone permissions and login Secrets. Removing these quotas restores admission without this demo VM-count cap.

Inspect state, or rehearse all three policies together:

```bash
python3 scripts/compliance-demo.py status --aro-context ARO_CONTEXT --rosa-context ROSA_CONTEXT
python3 scripts/compliance-demo.py enforce --aro-context ARO_CONTEXT --rosa-context ROSA_CONTEXT
```

An optional quota admission check requires Enforce to have created the quota and an empty selected project:

```bash
python3 scripts/verify-vm-quota.py --context ARO_CONTEXT --namespace linux-vms-prod
python3 scripts/verify-vm-quota.py --context ROSA_CONTEXT --namespace linux-vms-prod
```

The admission checker creates only temporary halted definitions, tests rejection of a third request and removes its own definitions in a `finally` block. Never start those diskless admission probes; they exist only to exercise object-count admission.

To install this package on the current demo setup:

```bash
oc --context ARO_CONTEXT apply -f governance/compliance-demo/projects.yaml
oc --context ROSA_CONTEXT apply -f governance/compliance-demo/projects.yaml
oc --context ARO_CONTEXT apply -k governance/compliance-demo
```

The existing `governance/policy.yaml` supplies the hub namespace, ManagedClusterSetBinding and placement. These policies are managed directly by ACM for the presentation; no GitOps application reconciles their remediation mode back to Inform. GitOps continues managing the VM specifications.

References: [ACM governance actions and parent remediation override](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.12/html-single/governance/index), [Kubernetes custom-resource count quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/).
