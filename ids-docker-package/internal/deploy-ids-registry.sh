#!/usr/bin/env bash

set -euo pipefail

IMAGE_PREFIX="${1:-}"
TAG="${2:-latest}"
shift $(( $# > 0 ? 1 : 0 )) || true
shift $(( $# > 0 ? 1 : 0 )) || true

if [[ -z "$IMAGE_PREFIX" ]]; then
  echo "用法: ./deploy-ids-registry.sh <image-prefix> [tag] [--single-repo] [deploy-runtime-options...]" >&2
  echo "示例: ./deploy-ids-registry.sh docker.io/yourname/campus-ids v1 --use-defaults --skip-start" >&2
  echo "示例: ./deploy-ids-registry.sh registry.cn-hangzhou.aliyuncs.com/ns/repo v1 --single-repo --use-defaults" >&2
  exit 1
fi

single_repo=0
skip_start_requested=0
runtime_args=()

for arg in "$@"; do
  case "$arg" in
    --single-repo) single_repo=1 ;;
    --skip-start) skip_start_requested=1 ;;
    *) runtime_args+=("$arg") ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd "$script_dir/.." && pwd)"
runtime_script="$script_dir/deploy-ids-runtime.sh"
compose_path="$package_root/docker-compose.generated.yml"
registry_compose_path="$package_root/docker-compose.registry.generated.yml"

if [[ "$single_repo" == "1" ]]; then
  runtime_image="${IMAGE_PREFIX}:runtime-${TAG}"
  frontend_image="${IMAGE_PREFIX}:frontend-${TAG}"
else
  runtime_image="${IMAGE_PREFIX}-runtime:${TAG}"
  frontend_image="${IMAGE_PREFIX}-frontend:${TAG}"
fi

"$runtime_script" "${runtime_args[@]}" --skip-start

python - "$compose_path" "$registry_compose_path" "$runtime_image" "$frontend_image" <<'PY'
from pathlib import Path
import sys

compose_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
runtime_image = sys.argv[3]
frontend_image = sys.argv[4]

content = compose_path.read_text(encoding="utf-8")
content = content.replace("ids-backend:\n    build:\n      context: ./ids-backend", f"ids-backend:\n    image: {runtime_image}")
content = content.replace("ids-gateway:\n    build:\n      context: ./ids-backend", f"ids-gateway:\n    image: {runtime_image}")
content = content.replace("ids-frontend:\n    build:\n      context: ./ids-frontend", f"ids-frontend:\n    image: {frontend_image}")
target_path.write_text(content, encoding="utf-8")
PY

echo "拉取运行镜像: $runtime_image"
docker pull "$runtime_image"
echo "拉取前端镜像: $frontend_image"
docker pull "$frontend_image"
docker compose --project-directory "$package_root" -f "$registry_compose_path" config >/dev/null

if [[ "$skip_start_requested" == "1" ]]; then
  echo "[info] 已生成 registry 部署编排文件并完成镜像拉取，未启动容器。"
  exit 0
fi

docker compose --project-directory "$package_root" -f "$registry_compose_path" up -d
echo "镜像部署完成。"
