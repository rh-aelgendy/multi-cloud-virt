# 15-minute presentation

All build execution is on ARO. Present from ARO's Console, GitOps and ACM UIs. Have a completed Windows build and two ready runtime VMs before the session.

| Time | Action | Message |
|---|---|---|
| 0–2 | Show ARO and ROSA HCP in ACM | “Separate cloud infrastructure; one operating process.” |
| 2–5 | Launch a fresh ARO PipelineRun from the prepared YAML sample, then explicitly switch to a completed run | “The platform builds and checks Team X's Windows standard.” |
| 5–7 | Show guest validation, local ARO boot source and ACM-staged ROSA boot source | “The image is built once and available locally at both destinations.” |
| 7–10 | Show the common VM base and cloud overlays in GitOps; open both IIS pages | “Same image version and team experience; different storage and VM identities.” |
| 10–12 | Remove the Linux VM ownership label and observe GitOps self-healing | “The same desired-state workflow corrects drift across clouds.” |
| 12–14 | Inspect/restart through ACM's fleet virtualization view | “Provisioning and day-two operations share an operating model.” |
| 14–15 | Return to the healthy fleet and application pages | “Build once. Stage locally. Provision consistently. Manage centrally.” |

Rehearse these points:

- The PipelineRun sample retains service account, placement, ISO security override and workspace.
- An ARO builder and runtime VM land only on `workload=virt`; the ROSA VM lands on metal.
- Both Windows pages show expected cloud/hostname and the same image version.
- Guest-agent and HTTP readiness survive restart.
- Both local DataSources are usable; no temporary export endpoint is needed after staging.
- Use `team-x-linux-rosa` for the label-drift moment: its automated self-healing is enabled and was verified. Windows applications use explicit manual sync.
- Presenter RBAC permits live resource edit and fleet VM actions.
- Explain that ROSA's DR role is hypothetical: no application-data replication or automatic failover is demonstrated.
- GitOps credentials and PVCs remain valid beyond the presentation date, until explicitly revoked/deleted.

Keep a clearly labeled recording of a real successful run as a connectivity fallback. Never describe a prepared run as the new live run. If the live build is still running at the end, leave it visible as ongoing work.

The setup history has a successful build/image-copy run whose final feedback wait was cancelled after an ACM parser correction, followed by successful completion run `team-x-image-complete-mrm82`. Show the successful installation/validation tasks and the separate completion result accurately. A future fresh run uses the corrected parser; this setup history is not a single entirely green PipelineRun.
