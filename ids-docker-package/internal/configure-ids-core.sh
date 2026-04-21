#!/usr/bin/env bash

set -euo pipefail

USE_DEFAULTS=0
SKIP_START=0
DEPLOY_MODE=""
CONSOLE_PORT=""
API_PORT=""
GATEWAY_PORT=""
FRONTEND_IP=""
FRONTEND_PORT=""
BACKEND_IP=""
BACKEND_PORT=""
DEFAULT_SITE_KEY=""
DEFAULT_SITE_NAME=""
DISPLAY_SITE_LABEL=""
DOMAIN_CODE=""
IMAGE_PREFIX=""
IMAGE_TAG="latest"
SINGLE_REPO=0
SINGLE_REPO_SET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --use-defaults)
      USE_DEFAULTS=1
      shift
      ;;
    --skip-start)
      SKIP_START=1
      shift
      ;;
    --deploy-mode)
      DEPLOY_MODE="${2:-}"
      shift 2
      ;;
    --console-port)
      CONSOLE_PORT="${2:-}"
      shift 2
      ;;
    --api-port)
      API_PORT="${2:-}"
      shift 2
      ;;
    --gateway-port)
      GATEWAY_PORT="${2:-}"
      shift 2
      ;;
    --frontend-ip)
      FRONTEND_IP="${2:-}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:-}"
      shift 2
      ;;
    --backend-ip)
      BACKEND_IP="${2:-}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="${2:-}"
      shift 2
      ;;
    --default-site-key)
      DEFAULT_SITE_KEY="${2:-}"
      shift 2
      ;;
    --default-site-name)
      DEFAULT_SITE_NAME="${2:-}"
      shift 2
      ;;
    --display-site-label)
      DISPLAY_SITE_LABEL="${2:-}"
      shift 2
      ;;
    --domain-code)
      DOMAIN_CODE="${2:-}"
      shift 2
      ;;
    --image-prefix)
      IMAGE_PREFIX="${2:-}"
      shift 2
      ;;
    --image-tag)
      IMAGE_TAG="${2:-latest}"
      shift 2
      ;;
    --single-repo)
      SINGLE_REPO=1
      SINGLE_REPO_SET=1
      shift
      ;;
    --dual-repo)
      SINGLE_REPO=0
      SINGLE_REPO_SET=1
      shift
      ;;
    *)
      echo "[error] unknown option: $1" >&2
      exit 1
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd "$script_dir/.." && pwd)"
local_script="$script_dir/deploy-ids-runtime.sh"
registry_script="$script_dir/deploy-ids-registry.sh"

write_section() {
  local title="$1"
  local description="${2:-}"
  printf '\n========================================================================\n'
  printf '%s\n' "$title"
  if [[ -n "$description" ]]; then
    printf '%s\n' "$description"
  fi
  printf '========================================================================\n'
}

trim() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

prompt_text() {
  local label="$1"
  local default_value="${2:-}"
  local allow_empty="${3:-0}"

  if [[ "$USE_DEFAULTS" == "1" ]]; then
    printf '%s' "$default_value"
    return
  fi

  local input=""
  while true; do
    if [[ -n "$default_value" ]]; then
      read -r -p "$label [$default_value]: " input
    else
      read -r -p "$label: " input
    fi
    input="$(trim "$input")"
    if [[ -z "$input" ]]; then
      if [[ "$allow_empty" == "1" ]]; then
        printf ''
        return
      fi
      if [[ -n "$default_value" ]]; then
        printf '%s' "$default_value"
        return
      fi
      echo "Please enter a value."
      continue
    fi
    printf '%s' "$input"
    return
  done
}

prompt_port() {
  local label="$1"
  local default_value="$2"

  if [[ "$USE_DEFAULTS" == "1" ]]; then
    printf '%s' "$default_value"
    return
  fi

  local input=""
  while true; do
    read -r -p "$label [$default_value]: " input
    input="$(trim "$input")"
    if [[ -z "$input" ]]; then
      printf '%s' "$default_value"
      return
    fi
    if [[ "$input" =~ ^[0-9]+$ ]] && (( input >= 1 && input <= 65535 )); then
      printf '%s' "$input"
      return
    fi
    echo "Port must be an integer between 1 and 65535."
  done
}

prompt_choice() {
  local label="$1"
  local default_value="$2"
  shift 2
  local options=("$@")

  if [[ "$USE_DEFAULTS" == "1" ]]; then
    printf '%s' "$default_value"
    return
  fi

  local input=""
  while true; do
    read -r -p "$label [$default_value] (${options[*]}): " input
    input="$(trim "$input")"
    if [[ -z "$input" ]]; then
      printf '%s' "$default_value"
      return
    fi
    input="${input,,}"
    local option
    for option in "${options[@]}"; do
      if [[ "$input" == "${option,,}" ]]; then
        printf '%s' "$option"
        return
      fi
    done
    echo "Please choose one of: ${options[*]}"
  done
}

prompt_bool() {
  local label="$1"
  local default_value="${2:-false}"
  local hint="y/N"

  if [[ "$default_value" == "true" ]]; then
    hint="Y/n"
  fi

  if [[ "$USE_DEFAULTS" == "1" ]]; then
    printf '%s' "$default_value"
    return
  fi

  local input=""
  while true; do
    read -r -p "$label [$hint]: " input
    input="$(trim "$input")"
    case "${input,,}" in
      "") printf '%s' "$default_value"; return ;;
      y|yes|1|true|on) printf 'true'; return ;;
      n|no|0|false|off) printf 'false'; return ;;
      *) echo "Please enter y or n." ;;
    esac
  done
}

default_deploy_mode="$DEPLOY_MODE"
if [[ -z "$default_deploy_mode" ]]; then
  if [[ -n "$IMAGE_PREFIX" ]]; then
    default_deploy_mode="registry"
  else
    default_deploy_mode="local"
  fi
fi

deploy_mode="$(prompt_choice 'Deployment mode' "$default_deploy_mode" local registry)"
console_port="${CONSOLE_PORT:-5175}"
api_port="${API_PORT:-8170}"
gateway_port="${GATEWAY_PORT:-8188}"
frontend_ip="${FRONTEND_IP:-127.0.0.1}"
frontend_port="${FRONTEND_PORT:-5173}"
backend_ip="${BACKEND_IP:-127.0.0.1}"
backend_port="${BACKEND_PORT:-8166}"
default_site_key="${DEFAULT_SITE_KEY:-campus_supply_chain}"
default_site_name="${DEFAULT_SITE_NAME:-校园供应链}"
display_site_label="${DISPLAY_SITE_LABEL:-校园供应链主站}"
domain_code="${DOMAIN_CODE:-Campus-Link-A}"

write_section "Core Deployment Config" "Only the parameters that actually affect ports, upstream targets and deployment source are shown here."
console_port="$(prompt_port 'IDS console port' "$console_port")"
api_port="$(prompt_port 'IDS API port' "$api_port")"
gateway_port="$(prompt_port 'IDS gateway port' "$gateway_port")"
frontend_ip="$(prompt_text 'Frontend upstream IP' "$frontend_ip")"
frontend_port="$(prompt_port 'Frontend upstream port' "$frontend_port")"
backend_ip="$(prompt_text 'Backend upstream IP' "$backend_ip")"
backend_port="$(prompt_port 'Backend upstream port' "$backend_port")"
default_site_key="$(prompt_text 'Default site key' "$default_site_key")"
default_site_name="$(prompt_text 'Default site name' "$default_site_name")"
display_site_label="$(prompt_text 'Display site label' "$display_site_label")"
domain_code="$(prompt_text 'Domain code' "$domain_code")"

common_args=(
  --use-defaults
  --console-port "$console_port"
  --api-port "$api_port"
  --gateway-port "$gateway_port"
  --frontend-ip "$frontend_ip"
  --frontend-port "$frontend_port"
  --backend-ip "$backend_ip"
  --backend-port "$backend_port"
  --default-site-key "$default_site_key"
  --default-site-name "$default_site_name"
  --display-site-label "$display_site_label"
  --domain-code "$domain_code"
)

if [[ "$SKIP_START" == "1" ]]; then
  common_args+=(--skip-start)
fi

if [[ "$deploy_mode" == "registry" ]]; then
  image_prefix="$(prompt_text 'Registry image prefix' "$IMAGE_PREFIX")"
  if [[ -z "$image_prefix" ]]; then
    echo "[error] Registry image prefix is required when deployment mode is registry." >&2
    exit 1
  fi
  image_tag="$(prompt_text 'Registry image tag' "$IMAGE_TAG")"

  if [[ "$SINGLE_REPO_SET" == "1" ]]; then
    single_repo_value=$([[ "$SINGLE_REPO" == "1" ]] && echo true || echo false)
  else
    single_repo_value=true
  fi
  single_repo_value="$(prompt_bool 'Use single-repo layout' "$single_repo_value")"

  write_section "Registry Image Source" "Provide only the real image location. Everything else stays on defaults unless you override it."
  printf 'Deploy mode: %s\n' "$deploy_mode"
  printf 'Image prefix: %s\n' "$image_prefix"
  printf 'Image tag: %s\n' "$image_tag"

  registry_args=("$image_prefix" "$image_tag")
  if [[ "$single_repo_value" == "true" ]]; then
    registry_args+=(--single-repo)
  fi
  registry_args+=("${common_args[@]}")
  exec "$registry_script" "${registry_args[@]}"
else
  write_section "Local Build Source" "The deployment will build the backend and frontend images from the current package directory."
  printf 'Deploy mode: %s\n' "$deploy_mode"
  exec "$local_script" "${common_args[@]}"
fi
