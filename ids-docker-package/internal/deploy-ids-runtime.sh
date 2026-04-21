#!/usr/bin/env bash

set -euo pipefail

USE_DEFAULTS=0
SKIP_START=0
CONSOLE_PORT_OVERRIDE=""
API_PORT_OVERRIDE=""
GATEWAY_PORT_OVERRIDE=""
FRONTEND_IP_OVERRIDE=""
FRONTEND_PORT_OVERRIDE=""
BACKEND_IP_OVERRIDE=""
BACKEND_PORT_OVERRIDE=""
DEFAULT_SITE_KEY_OVERRIDE=""
DEFAULT_SITE_NAME_OVERRIDE=""
DISPLAY_SITE_LABEL_OVERRIDE=""
DOMAIN_CODE_OVERRIDE=""

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
    --console-port)
      CONSOLE_PORT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --api-port)
      API_PORT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --gateway-port)
      GATEWAY_PORT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --frontend-ip)
      FRONTEND_IP_OVERRIDE="${2:-}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --backend-ip)
      BACKEND_IP_OVERRIDE="${2:-}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --default-site-key)
      DEFAULT_SITE_KEY_OVERRIDE="${2:-}"
      shift 2
      ;;
    --default-site-name)
      DEFAULT_SITE_NAME_OVERRIDE="${2:-}"
      shift 2
      ;;
    --display-site-label)
      DISPLAY_SITE_LABEL_OVERRIDE="${2:-}"
      shift 2
      ;;
    --domain-code)
      DOMAIN_CODE_OVERRIDE="${2:-}"
      shift 2
      ;;
    *)
      echo "[error] unknown option: $1" >&2
      exit 1
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd "$script_dir/.." && pwd)"
config_dir="$package_root/config"
data_dir="$package_root/ids-data"
state_dir="$data_dir/state"
env_example_path="$config_dir/ids-backend.env.example"
env_path="$config_dir/ids-backend.env"
state_path="$state_dir/communication_settings.json"
compose_path="$package_root/docker-compose.generated.yml"

mkdir -p "$config_dir" "$state_dir"

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

to_int_or_default() {
  local value="${1:-}"
  local default_value="$2"
  if [[ "$value" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )); then
    printf '%s' "$value"
  else
    printf '%s' "$default_value"
  fi
}

json_escape() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

bool_to_json() {
  local value="${1:-false}"
  case "$value" in
    1|true|TRUE|yes|YES|on|ON) printf 'true' ;;
    *) printf 'false' ;;
  esac
}

get_env_value() {
  local key="$1"
  local file_path="$2"
  if [[ ! -f "$file_path" ]]; then
    return 1
  fi

  local line
  line="$(grep -E "^${key}=" "$file_path" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 1
  fi

  printf '%s' "${line#*=}"
}

parse_upstream_url() {
  local raw_url="${1:-}"
  local fallback_host="$2"
  local fallback_port="$3"
  local normalized host port

  normalized="$(trim "$raw_url")"
  if [[ -z "$normalized" ]]; then
    printf '%s %s\n' "$fallback_host" "$fallback_port"
    return
  fi

  normalized="${normalized#http://}"
  normalized="${normalized#https://}"
  normalized="${normalized%%/*}"

  if [[ "$normalized" == *:* ]]; then
    host="${normalized%:*}"
    port="${normalized##*:}"
  else
    host="$normalized"
    port="$fallback_port"
  fi

  host="$(trim "$host")"
  port="$(to_int_or_default "$port" "$fallback_port")"

  if [[ -z "$host" ]]; then
    host="$fallback_host"
  fi

  printf '%s %s\n' "$host" "$port"
}

build_upstream_url() {
  local host_name
  host_name="$(trim "${1:-}")"
  local port="$2"
  printf 'http://%s:%s' "$host_name" "$port"
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
      echo "请输入内容。"
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
    echo "端口必须是 1-65535 之间的整数。"
  done
}

prompt_count() {
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
    if [[ "$input" =~ ^[0-9]+$ ]]; then
      printf '%s' "$input"
      return
    fi
    echo "请输入大于等于 0 的整数。"
  done
}

prompt_bool() {
  local label="$1"
  local default_value="${2:-false}"
  local prompt_hint="y/N"

  if [[ "$default_value" == "true" ]]; then
    prompt_hint="Y/n"
  fi

  if [[ "$USE_DEFAULTS" == "1" ]]; then
    printf '%s' "$default_value"
    return
  fi

  local input=""
  while true; do
    read -r -p "$label [$prompt_hint]: " input
    input="$(trim "$input")"
    if [[ -z "$input" ]]; then
      printf '%s' "$default_value"
      return
    fi
    case "${input,,}" in
      y|yes|1|true|on) printf 'true'; return ;;
      n|no|0|false|off) printf 'false'; return ;;
      *) echo "请输入 y 或 n。" ;;
    esac
  done
}

join_by_comma() {
  local first=1
  local item
  for item in "$@"; do
    if [[ $first -eq 1 ]]; then
      printf '%s' "$item"
      first=0
    else
      printf ',%s' "$item"
    fi
  done
}

ensure_unique_ports() {
  local default_port="$1"
  shift || true
  local seen=",$default_port,"
  local port
  for port in "$@"; do
    [[ -z "$port" ]] && continue
    if [[ "$seen" == *",$port,"* ]]; then
      echo "[error] 检测到重复入口端口: $port" >&2
      exit 1
    fi
    seen="${seen}${port},"
  done
}

ensure_unique_hosts() {
  local seen=","
  local host
  for host in "$@"; do
    [[ -z "$host" ]] && continue
    if [[ "$seen" == *",$host,"* ]]; then
      echo "[error] 检测到重复域名入口: $host" >&2
      exit 1
    fi
    seen="${seen}${host},"
  done
}

json_array_of_strings() {
  local items=("$@")
  if (( ${#items[@]} == 0 )); then
    printf '[]'
    return
  fi

  local escaped=()
  local item
  for item in "${items[@]}"; do
    escaped+=("\"$(json_escape "$item")\"")
  done

  printf '[%s]' "$(join_by_comma "${escaped[@]}")"
}

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] 未检测到 docker，请先安装 Docker Engine 或 Docker Desktop。" >&2
  exit 1
fi

env_gateway_port="$(to_int_or_default "$(get_env_value 'IDS_GATEWAY_DEFAULT_PORT' "$env_path" || true)" 8188)"
read -r env_frontend_host env_frontend_port <<<"$(parse_upstream_url "$(get_env_value 'IDS_GATEWAY_FRONTEND_BASE_URL' "$env_path" || true)" "127.0.0.1" 5173)"
read -r env_backend_host env_backend_port <<<"$(parse_upstream_url "$(get_env_value 'IDS_GATEWAY_BACKEND_BASE_URL' "$env_path" || true)" "127.0.0.1" 8166)"

default_gateway_port="$env_gateway_port"
default_frontend_ip="$env_frontend_host"
default_frontend_port="$env_frontend_port"
default_backend_ip="$env_backend_host"
default_backend_port="$env_backend_port"
default_site_key="campus_supply_chain"
default_site_name="校园供应链"
default_display_site_label="校园供应链主站"
default_domain_code="Campus-Link-A"
default_link_template="教学业务链路"
default_routing_profile="双向会话镜像"
default_packet_profile="HTTP 会话封装"
default_signal_band="基础频段"
default_coordination_group="校内协同单元"
default_display_mode="总控视图"
default_session_track_mode="连续轮转"
default_trace_color_mode="分层染色"
default_link_sync_clock="边界同步时钟"
default_relay_group="north-gateway"
default_auto_rotate="true"
default_popup_broadcast="true"
default_packet_shadow="true"
default_link_keepalive="true"

console_port="${CONSOLE_PORT_OVERRIDE:-5175}"
api_port="${API_PORT_OVERRIDE:-8170}"
gateway_port="${GATEWAY_PORT_OVERRIDE:-$default_gateway_port}"
frontend_ip="${FRONTEND_IP_OVERRIDE:-$default_frontend_ip}"
frontend_port="${FRONTEND_PORT_OVERRIDE:-$default_frontend_port}"
backend_ip="${BACKEND_IP_OVERRIDE:-$default_backend_ip}"
backend_port="${BACKEND_PORT_OVERRIDE:-$default_backend_port}"
default_site_key_value="${DEFAULT_SITE_KEY_OVERRIDE:-$default_site_key}"
default_site_name_value="${DEFAULT_SITE_NAME_OVERRIDE:-$default_site_name}"
display_site_label_value="${DISPLAY_SITE_LABEL_OVERRIDE:-$default_display_site_label}"
domain_code_value="${DOMAIN_CODE_OVERRIDE:-$default_domain_code}"

write_section "IDS Docker 通信配置启动器" "将边界安全防线、核心业务平台和通信编排能力统一生成到 Docker 部署文件中。"

write_section "第二阶段｜边界安全防线" "配置默认入口、核心站点回源和 IDS 网关监听关系。这一组参数会真正决定流量怎样先经过 IDS 再进入目标站点。"
gateway_port="$(prompt_port '默认入口端口' "$gateway_port")"
frontend_ip="$(prompt_text '默认前端回源 IP' "$frontend_ip")"
frontend_port="$(prompt_port '默认前端回源端口' "$frontend_port")"
backend_ip="$(prompt_text '默认后端回源 IP' "$backend_ip")"
backend_port="$(prompt_port '默认后端回源端口' "$backend_port")"
default_site_key_value="$(prompt_text '默认站点标识' "$default_site_key_value")"
default_site_name_value="$(prompt_text '默认站点名称' "$default_site_name_value")"

write_section "第三阶段｜核心业务平台" "配置 IDS 控制台端口与 API 入口，用于容器化后的统一管理与状态查看。"
console_port="$(prompt_port 'IDS 控制台对外端口' "$console_port")"
api_port="$(prompt_port 'IDS API 对外端口' "$api_port")"

write_section "第五阶段｜全流程联调与闭环验证" "可选配置多站点端口入口和域名入口，适用于一套 IDS 管理多个业务入口的场景。"

edit_port_mappings="$(prompt_bool '是否重新配置附加端口入口映射' 'false')"
port_mapping_objects=()
port_mapping_ports=()
if [[ "$edit_port_mappings" == "true" ]]; then
  port_count="$(prompt_count '附加端口入口数量' 0)"
  for (( i=0; i<port_count; i++ )); do
    printf '\n附加端口入口 #%s\n' "$((i + 1))"
    site_key="$(prompt_text '  站点标识' "site_$((i + 1))")"
    display_name="$(prompt_text '  站点名称' "附加站点 $((i + 1))")"
    ingress_port="$(prompt_port '  入口端口' "$((8288 + i * 100))")"
    extra_frontend_ip="$(prompt_text '  前端回源 IP' "$frontend_ip")"
    extra_frontend_port="$(prompt_port '  前端回源端口' "$frontend_port")"
    extra_backend_ip="$(prompt_text '  后端回源 IP' "$backend_ip")"
    extra_backend_port="$(prompt_port '  后端回源端口' "$backend_port")"

    frontend_upstream="$(build_upstream_url "$extra_frontend_ip" "$extra_frontend_port")"
    backend_upstream="$(build_upstream_url "$extra_backend_ip" "$extra_backend_port")"

    port_mapping_objects+=("{\"site_key\":\"$(json_escape "$site_key")\",\"display_name\":\"$(json_escape "$display_name")\",\"ingress_port\":$ingress_port,\"frontend_upstream\":\"$(json_escape "$frontend_upstream")\",\"backend_upstream\":\"$(json_escape "$backend_upstream")\"}")
    port_mapping_ports+=("$ingress_port")
  done
fi

edit_host_mappings="$(prompt_bool '是否重新配置域名入口映射' 'false')"
host_mapping_objects=()
host_mapping_hosts=()
if [[ "$edit_host_mappings" == "true" ]]; then
  host_count="$(prompt_count '域名入口数量' 0)"
  for (( i=0; i<host_count; i++ )); do
    printf '\n域名入口 #%s\n' "$((i + 1))"
    site_key="$(prompt_text '  站点标识' "host_$((i + 1))")"
    display_name="$(prompt_text '  站点名称' "域名站点 $((i + 1))")"
    hosts_csv="$(prompt_text '  域名列表(逗号分隔)' '')"
    host_frontend_ip="$(prompt_text '  前端回源 IP' "$frontend_ip")"
    host_frontend_port="$(prompt_port '  前端回源端口' "$frontend_port")"
    host_backend_ip="$(prompt_text '  后端回源 IP' "$backend_ip")"
    host_backend_port="$(prompt_port '  后端回源端口' "$backend_port")"

    IFS=',' read -r -a raw_hosts <<<"$hosts_csv"
    host_items=()
    for raw_host in "${raw_hosts[@]}"; do
      normalized_host="$(trim "${raw_host,,}")"
      normalized_host="${normalized_host%.}"
      if [[ -n "$normalized_host" ]]; then
        host_items+=("$normalized_host")
        host_mapping_hosts+=("$normalized_host")
      fi
    done

    if (( ${#host_items[@]} == 0 )); then
      echo "[warn] 域名入口 #$((i + 1)) 未填写有效域名，已跳过。"
      continue
    fi

    frontend_upstream="$(build_upstream_url "$host_frontend_ip" "$host_frontend_port")"
    backend_upstream="$(build_upstream_url "$host_backend_ip" "$host_backend_port")"
    hosts_json="$(json_array_of_strings "${host_items[@]}")"
    host_mapping_objects+=("{\"site_key\":\"$(json_escape "$site_key")\",\"display_name\":\"$(json_escape "$display_name")\",\"hosts\":$hosts_json,\"frontend_upstream\":\"$(json_escape "$frontend_upstream")\",\"backend_upstream\":\"$(json_escape "$backend_upstream")\"}")
  done
fi

ensure_unique_ports "$gateway_port" "${port_mapping_ports[@]}"
ensure_unique_hosts "${host_mapping_hosts[@]}"

write_section "第四阶段｜纵深主动防御与通信编排" "这一组参数主要服务于通信配置中心、大屏、链路命名和态势编排展示；只有前面那组入口与回源参数直接改变转发路径。"

edit_display_settings="$(prompt_bool '是否进入扩展通信编排配置' 'false')"
if [[ "$edit_display_settings" == "true" ]]; then
  display_site_label_value="$(prompt_text '站点名称' "$display_site_label_value")"
  domain_code_value="$(prompt_text '通信域编号' "$domain_code_value")"
  default_link_template="$(prompt_text '链路模板' "$default_link_template")"
  default_routing_profile="$(prompt_text '路由编排' "$default_routing_profile")"
  default_packet_profile="$(prompt_text '会话封装' "$default_packet_profile")"
  default_signal_band="$(prompt_text '频段标签' "$default_signal_band")"
  default_coordination_group="$(prompt_text '协同分组' "$default_coordination_group")"
  default_display_mode="$(prompt_text '展示模式' "$default_display_mode")"
  default_session_track_mode="$(prompt_text '会话轮转' "$default_session_track_mode")"
  default_trace_color_mode="$(prompt_text '轨迹染色' "$default_trace_color_mode")"
  default_link_sync_clock="$(prompt_text '同步时钟' "$default_link_sync_clock")"
  default_relay_group="$(prompt_text '中继分组' "$default_relay_group")"
  default_auto_rotate="$(prompt_bool '自动轮转' "$default_auto_rotate")"
  default_popup_broadcast="$(prompt_bool '弹窗播报' "$default_popup_broadcast")"
  default_packet_shadow="$(prompt_bool '数据包影子副本' "$default_packet_shadow")"
  default_link_keepalive="$(prompt_bool '链路保活' "$default_link_keepalive")"
fi

frontend_upstream="$(build_upstream_url "$frontend_ip" "$frontend_port")"
backend_upstream="$(build_upstream_url "$backend_ip" "$backend_port")"

port_mappings_json='[]'
if (( ${#port_mapping_objects[@]} > 0 )); then
  port_mappings_json="[$(join_by_comma "${port_mapping_objects[@]}")]"
fi

host_mappings_json='[]'
if (( ${#host_mapping_objects[@]} > 0 )); then
  host_mappings_json="[$(join_by_comma "${host_mapping_objects[@]}")]"
fi

display_json="$(cat <<EOF
{
  "site_label": "$(json_escape "$display_site_label_value")",
  "domain_code": "$(json_escape "$domain_code_value")",
  "link_template": "$(json_escape "$default_link_template")",
  "routing_profile": "$(json_escape "$default_routing_profile")",
  "packet_profile": "$(json_escape "$default_packet_profile")",
  "signal_band": "$(json_escape "$default_signal_band")",
  "coordination_group": "$(json_escape "$default_coordination_group")",
  "display_mode": "$(json_escape "$default_display_mode")",
  "session_track_mode": "$(json_escape "$default_session_track_mode")",
  "trace_color_mode": "$(json_escape "$default_trace_color_mode")",
  "link_sync_clock": "$(json_escape "$default_link_sync_clock")",
  "relay_group": "$(json_escape "$default_relay_group")",
  "auto_rotate": $(bool_to_json "$default_auto_rotate"),
  "popup_broadcast": $(bool_to_json "$default_popup_broadcast"),
  "packet_shadow": $(bool_to_json "$default_packet_shadow"),
  "link_keepalive": $(bool_to_json "$default_link_keepalive")
}
EOF
)"

cat >"$state_path" <<EOF
{
  "real": {
    "gateway_port": $gateway_port,
    "frontend_ip": "$(json_escape "$frontend_ip")",
    "frontend_port": $frontend_port,
    "backend_ip": "$(json_escape "$backend_ip")",
    "backend_port": $backend_port,
    "default_site_key": "$(json_escape "$default_site_key_value")",
    "default_site_name": "$(json_escape "$default_site_name_value")",
    "extra_port_sites": $port_mappings_json,
    "host_sites": $host_mappings_json
  },
  "display": $display_json,
  "updated_at": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

cat >"$env_path" <<EOF
# Generated by start-ids-docker.sh
# Generated at $(date '+%Y-%m-%d %H:%M:%S')

DATABASE_URL=sqlite:////data/ids.db
SECRET_KEY=change-this-ids-secret-in-production
IDS_DEFAULT_ADMIN_USERNAME=ids_admin
IDS_DEFAULT_ADMIN_PASSWORD=123456
IDS_DEFAULT_ADMIN_REAL_NAME=IDS Admin
IDS_ACCEPTED_UPLOAD_DIR=/data/uploads/accepted
IDS_QUARANTINE_DIR=/data/quarantine
IDS_REPORT_DIR=/data/reports
IDS_OPERATOR_STATE_DIR=/data/state
IDS_AI_ANALYSIS=true
IDS_BLOCK_THRESHOLD=70
IDS_INTEGRATION_TOKEN=
IDS_GATEWAY_DEFAULT_PORT=$gateway_port
IDS_GATEWAY_FRONTEND_BASE_URL=$frontend_upstream
IDS_GATEWAY_BACKEND_BASE_URL=$backend_upstream
IDS_GATEWAY_SITE_MAP=$host_mappings_json
IDS_GATEWAY_PORT_MAP=$port_mappings_json
LLM_PROVIDER=deepseek
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=deepseek-chat
CORS_ORIGINS=["http://localhost:$console_port","http://127.0.0.1:$console_port","http://localhost:8081","http://127.0.0.1:8081"]
EOF

gateway_port_lines="      - \"${gateway_port}:8188\""
if (( ${#port_mapping_ports[@]} > 0 )); then
  for port in "${port_mapping_ports[@]}"; do
    gateway_port_lines+=$'\n'"      - \"${port}:8188\""
  done
fi

cat >"$compose_path" <<EOF
services:
  ids-backend:
    build:
      context: ./ids-backend
    restart: unless-stopped
    ports:
      - "${api_port}:8170"
    volumes:
      - ./config/ids-backend.env:/app/.env
      - ./ids-data:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8170/api/health', timeout=5)"]
      interval: 15s
      timeout: 5s
      retries: 8
      start_period: 20s

  ids-gateway:
    build:
      context: ./ids-backend
    restart: unless-stopped
    command: ["uvicorn", "app.gateway_main:app", "--host", "0.0.0.0", "--port", "8188"]
    depends_on:
      ids-backend:
        condition: service_healthy
    volumes:
      - ./config/ids-backend.env:/app/.env
      - ./ids-data:/data
    ports:
$gateway_port_lines
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8188/gateway/health', timeout=5)"]
      interval: 15s
      timeout: 5s
      retries: 8
      start_period: 20s

  ids-frontend:
    build:
      context: ./ids-frontend
    restart: unless-stopped
    depends_on:
      ids-backend:
        condition: service_healthy
    ports:
      - "${console_port}:80"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/ || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 8
      start_period: 10s
EOF

write_section "第五阶段｜生成结果校验" "正在校验 Docker Compose 文件结构与容器依赖关系。"
docker compose --project-directory "$package_root" -f "$compose_path" config >/dev/null
echo "[ok] docker-compose.generated.yml 已通过语法校验。"

printf '\n重点运行参数\n'
printf '  默认入口端口: %s\n' "$gateway_port"
printf '  默认前端回源: %s\n' "$frontend_upstream"
printf '  默认后端回源: %s\n' "$backend_upstream"
printf '  附加端口入口数量: %s\n' "${#port_mapping_objects[@]}"
printf '  域名入口数量: %s\n' "${#host_mapping_objects[@]}"

printf '\n控制台编排参数\n'
printf '  站点名称: %s\n' "$display_site_label_value"
printf '  通信域编号: %s\n' "$domain_code_value"
printf '  链路模板: %s\n' "$default_link_template"
printf '  展示模式: %s\n' "$default_display_mode"

printf '\n配置文件: %s\n' "$env_path"
printf '状态文件: %s\n' "$state_path"
printf 'Compose 文件: %s\n' "$compose_path"

if [[ "$SKIP_START" == "1" ]]; then
  printf '\n[info] 已按要求仅生成配置文件，未启动 Docker 容器。\n'
  exit 0
fi

write_section "容器启动中" "将按当前通信配置拉起 IDS 后端、IDS 网关与 IDS 控制台。"
docker compose --project-directory "$package_root" -f "$compose_path" up -d --build

sleep 6

check_health() {
  local name="$1"
  local url="$2"
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 8 "$url" >/dev/null; then
      printf '  [ok] %s: %s\n' "$name" "$url"
      return
    fi
  elif command -v wget >/dev/null 2>&1; then
    if wget -q -T 8 -O /dev/null "$url"; then
      printf '  [ok] %s: %s\n' "$name" "$url"
      return
    fi
  fi
  printf '  [warn] %s: 启动后未立即通过探测 %s\n' "$name" "$url"
}

printf '\n服务探测结果\n'
check_health "IDS Frontend" "http://127.0.0.1:${console_port}/"
check_health "IDS Backend" "http://127.0.0.1:${api_port}/api/health"
check_health "IDS Gateway" "http://127.0.0.1:${gateway_port}/gateway/health"

ip_list=()
if command -v hostname >/dev/null 2>&1; then
  while IFS= read -r ip; do
    [[ -n "$ip" ]] && ip_list+=("$ip")
  done < <(hostname -I 2>/dev/null | tr ' ' '\n' | awk 'NF' || true)
fi

if (( ${#ip_list[@]} > 0 )); then
  printf '\n本机 IPv4 地址\n'
  for ip in "${ip_list[@]}"; do
    printf '  %s\n' "$ip"
  done

  printf '\n访问示例\n'
  local_count=0
  for ip in "${ip_list[@]}"; do
    printf '  IDS 网关:  http://%s:%s\n' "$ip" "$gateway_port"
    printf '  IDS 控制台: http://%s:%s\n' "$ip" "$console_port"
    local_count=$((local_count + 1))
    if (( local_count >= 2 )); then
      break
    fi
  done
fi

printf '\n如果后续你在 Web 通信配置中心改了默认入口端口或附加端口入口，请重新执行本脚本以重新生成 Docker 端口映射。\n'
