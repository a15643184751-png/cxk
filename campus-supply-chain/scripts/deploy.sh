#!/bin/bash
# 云服务器一键部署脚本（Docker Compose）
set -e
cd "$(dirname "$0")/.."

echo "==> 检查 Docker..."
which docker >/dev/null 2>&1 || { echo "请先安装 Docker"; exit 1; }
which docker compose >/dev/null 2>&1 || which docker-compose >/dev/null 2>&1 || { echo "请先安装 Docker Compose"; exit 1; }

echo "==> 创建 .env（若不存在）..."
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "已创建 .env，生产环境请修改 SECRET_KEY 后重新部署"
fi

echo "==> 构建并启动..."
docker compose up -d --build

echo "==> 等待后端就绪..."
sleep 5

echo "==> 初始化预置数据（若尚未初始化）..."
docker compose exec -T backend python init_db.py 2>/dev/null || echo "跳过或已初始化"

echo ""
echo "部署完成！"
echo "  前端: http://$(hostname -I 2>/dev/null | awk '{print $1}'):80 或 http://本机IP"
echo "  API: http://本机IP/docs"
