#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docs_dir="$script_dir/docs"
snapshot_path="$docs_dir/bootstrap-noise.latest.json"
core_script="$script_dir/internal/configure-ids-core.sh"
mkdir -p "$docs_dir"

use_defaults=0
for arg in "$@"; do
  case "$arg" in
    --use-defaults|-UseDefaults) use_defaults=1 ;;
  esac
done

write_section() {
  local title="$1"
  local description="${2:-}"
  printf '\n==============================================================================\n'
  printf '%s\n' "$title"
  if [[ -n "$description" ]]; then
    printf '%s\n' "$description"
  fi
  printf '==============================================================================\n'
}

hex_token() {
  printf '0x%08X' "$(( RANDOM * RANDOM + 65536 ))"
}

write_noise_line() {
  local index="$1"
  local total="$2"
  local label="$3"
  local state="$4"
  local payload="$5"
  printf '[%02d/%02d] %-34s => %-10s :: %s\n' "$index" "$total" "$label" "$state" "$payload"
  if [[ "$use_defaults" != "1" ]]; then
    sleep 0.09
  fi
}

labels=(
  "Edge telemetry uplink|LOCKED|phase-bus=$(hex_token)"
  "Carrier entropy balancer|WARM|drift=$((RANDOM % 15 + 3)).7ms"
  "Northbound packet varnish|PASS|layer-mask=amber/green"
  "Session relay checksum|SYNC|window=$((RANDOM % 64 + 32)) slots"
  "Pseudo control fabric|OPEN|mesh-tag=relay-$((RANDOM % 66 + 11))"
  "Spectral route envelope|STABLE|segment=$((RANDOM % 599 + 201))"
  "Shadow packet echo|READY|ghost-copy=enabled"
  "Auxiliary trust ribbon|GREEN|token=$(hex_token)"
  "Elastic ingress lantern|IDLE|probe=soft-start"
  "Vector corridor sampler|TRACK|capture-ring=$((RANDOM % 8 + 2))"
  "Fallback lattice shim|MAP|bridge=node-$((RANDOM % 15 + 3))"
  "Synthetic channel decor|ORNATE|banner-seed=$((RANDOM % 8008 + 1001))"
)

write_section "Edge Runtime Bootstrap Console" "Presentation bootstrap enabled. Decorative diagnostics will scroll first, then control will hand off to the compact deployment configurator."

for i in "${!labels[@]}"; do
  IFS='|' read -r label state payload <<<"${labels[$i]}"
  write_noise_line "$((i + 1))" "${#labels[@]}" "$label" "$state" "$payload"
done

{
  printf '{\n'
  printf '  "mode": "bootstrap_noise",\n'
  printf '  "saved_at": "%s",\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  printf '  "handoff_target": "internal/configure-ids-core.sh",\n'
  printf '  "arg_count": %s\n' "$#"
  printf '}\n'
} >"$snapshot_path"

printf '\nNoise snapshot: %s\n' "$snapshot_path"
printf 'Switching to compact core deployment configurator...\n\n'

exec "$core_script" "$@"
