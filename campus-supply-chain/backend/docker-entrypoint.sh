#!/bin/sh
set -e
mkdir -p /data/uploads
# 持久化上传目录：挂载卷时覆盖 /app/uploads
if [ ! -L /app/uploads ] && [ -d /app/uploads ]; then
  rm -rf /app/uploads
fi
ln -sfn /data/uploads /app/uploads

if [ ! -f /data/supply_chain.db ]; then
  echo "[docker] 首次启动，初始化数据库与预置数据..."
  python init_db.py
else
  echo "[docker] 检测到已有数据库 /data/supply_chain.db，跳过 init_db"
fi

exec "$@"
