#!/usr/bin/env bash
# 构建并推送到你的 Docker 仓库（需已 docker login）。
#
#   DOCKER_USER=你的DockerHub用户名 ./scripts/push-docker.sh
#   REGISTRY=registry.cn-hangzhou.aliyuncs.com/命名空间 ./scripts/push-docker.sh
#   TAG=v1.0.0 DOCKER_USER=myuser ./scripts/push-docker.sh
#
# 或位置参数（Docker Hub）：
#   ./scripts/push-docker.sh myuser [tag]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TAG="${TAG:-latest}"
PREFIX=""

if [[ -n "${REGISTRY:-}" ]]; then
  PREFIX="${REGISTRY%/}"
elif [[ -n "${DOCKER_USER:-}" ]]; then
  PREFIX="$DOCKER_USER"
elif [[ -n "${1:-}" ]]; then
  PREFIX="$1"
  TAG="${2:-$TAG}"
else
  echo "用法:" >&2
  echo "  DOCKER_USER=你的DockerHub用户名 ./scripts/push-docker.sh" >&2
  echo "  REGISTRY=registry.example.com/命名空间 ./scripts/push-docker.sh" >&2
  echo "  $0 <DockerHub用户名> [tag]" >&2
  exit 1
fi

export BACKEND_IMAGE="${PREFIX}/campus-supply-backend:${TAG}"
export FRONTEND_IMAGE="${PREFIX}/campus-supply-frontend:${TAG}"

echo "镜像将推送为:"
echo "  ${BACKEND_IMAGE}"
echo "  ${FRONTEND_IMAGE}"
echo ""
echo "若尚未登录，请先执行: docker login [仓库地址]"
echo ""

docker compose build
docker compose push
