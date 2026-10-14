# VM fleet right-sizing demo

Based on the Perses flow in rh-aelgendy/acm-hybrid-cloud-demo, adapted to real KubeVirt guest metrics rather than container request recommendations.

## Fixtures

`linux-oversized-aro` and `linux-oversized-rosa` run in `linux-vms-prod`. Each has 8 vCPU and 16 GiB RAM and runs the small HTTP demo application. ARO selects `workload=virt`; ROSA selects its existing m5zn.metal worker. Existing Windows VMs and the live GitOps ApplicationSet examples are separate.

These fixture VMs are deliberately managed directly by YAML so GitOps self-healing does not revert the live resize. Their default Fedora username is `fedora`; password is in the local cluster's `linux-vm-login` Secret, key `fedora`.

## Dashboard

Hub Console → Administrator → Observe → Dashboards (Perses), project `open-cluster-management-observability`, dashboard **VM Fleet — Right-sizing opportunities**. Refresh the browser after plugin installation.

The vCPU count is derived from distinct per-vCPU IDs in `kubevirt_vmi_vcpu_seconds_total`, available on both clusters (ROSA does not expose the convenience `kubevirt_vmi_vcpu_count` series). The scrape preserves those IDs. The dashboard compares assigned vCPU with observed CPU cores, and assigned RAM with guest used RAM. The candidate panel displays 1 for a VM when CPU peak is below 20% AND guest memory peak below 40% over the observed last 15 minutes, with at least 20 real guest-memory samples. At 30-second collection, allow about 10–15 minutes after guest telemetry starts. Missing series mean unavailable telemetry, never zero use. It also displays the sample count, running VM inventory and swap-out rate.

This is a transparent demo heuristic. ACM's native virtualization right-sizing analytics is also enabled. Use project `observability-analytics` → **ACM Right-Sizing OpenShift Virtualization VM Overestimation**, select cluster `acm-hub-aro` or `rosa-virt-dr`, namespace `linux-vms-prod`, VM `linux-oversized-*`, profile `Max OverAll`. Its recommendations come from ACM recording rules, independently of our simple heuristic. The VM aggregation rules run every 5 minutes, and historical recommendation groups every 15 minutes; leave it overnight for a more useful rehearsal history. Empty recommendations mean insufficient/unavailable data, never a zero-sized VM. The reference Perses integration is Technology Preview; namespace right-sizing is Developer Preview. Guest used memory excludes reclaimable cache; use representative peak history and workload tests before a production decision. No fabricated history or savings figures are used.

## Live show and tell

1. Show both oversized Linux VMs as candidates, grouped by cluster/project/VM. Compare 8 assigned vCPU and 16 GiB with actual use.
2. In the target cluster Console, Virtualization → VirtualMachines → `linux-vms-prod`, select that cluster's `linux-oversized-*` VM and **Stop**. Wait until Stopped.
3. Edit its YAML: `spec.template.spec.domain.cpu.cores: 2`, `domain.resources.requests.cpu: "2"`, `domain.resources.requests.memory: 2Gi`, and `domain.memory.guest: 2Gi`. Save and **Start**. Alternatively apply the matching `vm-*-optimized.json` while stopped, then start.
4. Verify Running/Ready and the guest HTTP readiness probe. Show the same dashboard's assigned-capacity step change. The 15-minute candidate window retains prior samples until they age out; a lightly used 2-core VM may still qualify, which is valid.
5. Reset after the session: Stop → apply matching `vm-aro.json` or `vm-rosa.json` → Start. Leave oversized overnight to collect history before the next session.

The illustrative change reduces assigned guest capacity by 6 vCPU and 14 GiB per VM. CPU requests are explicitly equal to assigned vCPU for these fixtures, so the scheduling reservation also decreases. This alone does not lower a cloud bill; the backing nodes and billing have not changed.

## Setup and retention

The private Azure Blob container holds Thanos metric history. Kubernetes PVCs use `managed-csi`, independent of the VM disks. No SAS URLs or short-lived tokens are used. Azure account keys and registry credentials stay in Kubernetes Secrets; storage details without credentials are recorded in ignored `.local/demo/vm-observability-storage.json`.

`multiclusterobservability.json` enables MCOA platform metrics, Perses integration and namespace and virtualization analytics. `scrapeconfig.json` federates only the six required VM metric families for the three demo projects. `dashboard.json` uses the generated `rbac-query-proxy-datasource` and preserves user authorization. The setup must attach the scrape reference to MCOA's existing placement configs without replacing other configs.

Normal demo reset keeps observability, Blob history and source disks. Do not delete Blob objects while Thanos owns the store.

Sources: [reference demo](https://github.com/rh-aelgendy/acm-hybrid-cloud-demo/tree/main/observability), [ACM 2.17 observability](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html/observability/observing-environments-intro), [KubeVirt metrics](https://kubevirt.io/monitoring/metrics.html).

### Reproduce setup

From this repository, with `oc` pointed at ARO and Azure CLI authenticated:

```bash
python3 scripts/setup-vm-observability-storage.py
oc apply --dry-run=server -f observability/multiclusterobservability.json
oc apply -f observability/multiclusterobservability.json
# Wait for ACM-managed Perses and ScrapeConfig APIs to be installed.
python3 scripts/configure-vm-observability.py
```

For each cluster, use its context and apply `observability/clone-rbac.json`, run `scripts/create-linux-login-secret.py --context CONTEXT --namespace linux-vms-prod --generate`, then apply that cluster's `observability/vm-aro.json` or `observability/vm-rosa.json`. The project must exist first. All manifests are JSON, which is valid YAML and can be pasted into Console Import YAML. Do not apply the entire directory at once: oversized and optimized examples target the same VM.
