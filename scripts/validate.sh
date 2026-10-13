#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
validation_tmp=$(mktemp -d)
trap 'rm -rf "$validation_tmp"' EXIT
oc kustomize pipelines > "$validation_tmp/pipelines.yaml"
oc kustomize vm/overlays/aro > "$validation_tmp/aro.yaml"
oc kustomize vm/overlays/rosa > "$validation_tmp/rosa.yaml"
ruby -ryaml -e '
  files = Dir.glob("{windows,pipelines,vm,gitops,governance,tools,console}/**/*.yaml") + Dir.glob(ARGV[0] + "/*.yaml")
  files.each { |file| YAML.load_stream(File.read(file)) }
  puts "Parsed #{files.length} YAML sources/rendered bundles"
  ["aro", "rosa"].each do |cloud|
    docs = YAML.load_stream(File.read("#{ARGV[0]}/#{cloud}.yaml"))
    vm = docs.find { |d| d["kind"] == "VirtualMachine" }
    service = docs.find { |d| d["kind"] == "Service" }
    raise "Incorrect namespace" unless docs.all? { |d| d.dig("metadata", "namespace") == "team-x" }
    template = vm.dig("spec", "template")
    selector = service.dig("spec", "selector")
    raise "Service selector mismatch" unless selector.all? { |k,v| template.dig("metadata", "labels", k) == v }
    disk = vm.dig("spec", "dataVolumeTemplates", 0, "metadata", "name")
    raise "Disk reference mismatch" unless template.dig("spec", "volumes", 0, "dataVolume", "name") == disk
    placement = template.dig("spec", "nodeSelector")
    if cloud == "aro"
      raise "ARO VM placement missing" unless placement == {"workload" => "virt"}
    else
      raise "ROSA metal placement missing" unless placement["node.kubernetes.io/instance-type"] == "m5zn.metal"
    end
    raise "External image source still configured" unless vm.dig("spec", "dataVolumeTemplates", 0, "spec", "sourceRef", "kind") == "DataSource"
    expected = cloud == "aro" ? "azure" : "aws"
    raise "Cloud label mismatch" unless vm.dig("metadata", "labels", "cloud") == expected
  end
  docs = YAML.load_stream(File.read("#{ARGV[0]}/pipelines.yaml"))
  pipeline = docs.find { |d| d["kind"] == "Pipeline" }
  task = docs.find { |d| d["kind"] == "Task" }
  names = pipeline.dig("spec", "tasks").map { |t| t["name"] }
  pipeline.dig("spec", "tasks").each do |t|
    raise "Missing task dependency" unless (t.fetch("runAfter", []) - names).empty?
    next unless t.dig("taskRef", "name") == task.dig("metadata", "name")
    required = task.dig("spec", "params").map { |p| p["name"] }
    supplied = t["params"].map { |p| p["name"] }
    raise "Task parameter mismatch" unless required.sort == supplied.sort
  end
  puts "Verified overlay selectors, disk references, cloud labels and task wiring"
' "$validation_tmp"
python3 -B scripts/test_factory.py
bash -n scripts/preflight.sh scripts/validate.sh
echo 'Offline validation passed. Cluster admission and Windows execution are still pending.'
