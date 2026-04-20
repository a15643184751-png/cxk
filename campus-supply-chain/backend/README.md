# 校园物资供应链 - 后端 API

## 技术栈

- FastAPI
- SQLAlchemy + SQLite（开发）/ PostgreSQL（生产）
- JWT 认证
- Pydantic

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库（创建表 + 用户/物资 + POCHAIN 完整链路预置数据）
python init_db.py

# 已有旧库、需清理历史垃圾单并重建「完整订单+溯源+库存」时：
python -m app.demo_dataset_cohesive --force

# 单号前缀 POCHAIN-*，溯源可查订单号或交接码；库存为 LOT-* 多批次。

# 3. 启动服务（本机）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8166

# 3b. 局域网其他设备访问 API 时，请监听所有网卡
uvicorn app.main:app --reload --host 0.0.0.0 --port 8166
```

前端开发服务器已配置 `host: true`，手机/同事电脑可用 `http://你的IP:5173` 打开；后端默认启用 `CORS_ALLOW_PRIVATE_NETWORKS`，会匹配常见内网 IPv4 来源。生产环境请在 `.env` 中设置 `CORS_ALLOW_PRIVATE_NETWORKS=false` 并收紧 `CORS_ORIGINS`。

## 预置账号（开发环境）

与 `init_db.py` 一致（密码均为 **123456**）：

| 用户名 | 角色 |
|--------|------|
| system_admin | 系统管理员 |
| logistics_admin | 后勤管理员 |
| warehouse_procurement | 仓储采购员 |
| campus_supplier | 校园供应商（已绑定预置供应商） |
| counselor_teacher | 辅导员/教师 |

旧用户名 `admin` / `procurement` / `supplier` / `teacher` 会在初始化时迁移到新角色。

## API 文档

启动后访问：http://localhost:8166/docs

## 前端代理

前端 `vite.config.ts` 已配置代理到 `http://127.0.0.1:8166`。
