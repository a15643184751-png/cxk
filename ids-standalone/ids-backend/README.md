# 独立 IDS 后端

这是从原“校园物资供应链平台”中拆出的独立 IDS 后端，只保留 IDS 所需的登录、鉴权、事件、上传审计、通知、AI 研判与审计能力。

## 目录职责

- `app/main.py`: 独立 FastAPI 入口，只挂载 `auth / ids / upload`
- `app/bootstrap.py`: 运行目录初始化、默认管理员初始化
- `init_ids_db.py`: 初始化独立 IDS 数据库
- `scripts/migrate_from_monolith.py`: 从旧单体 `backend/supply_chain.db` 迁移 IDS 数据与样本文件

## 本地启动

```bash
pip install -r requirements.txt
python init_ids_db.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8170
```

首次启动会自动创建默认管理员：

- 用户名：`ids_admin`
- 密码：`123456`

## 从旧单体迁移

默认迁移源会读取：

- `D:\ids\backend\supply_chain.db`
- `D:\ids\backend\uploads\accepted`
- `D:\ids\backend\quarantine_uploads`
- `D:\ids\backend\upload_reports`
- `D:\ids\backend\app\data\ids_operator_state`

执行：

```bash
python scripts/migrate_from_monolith.py
```

迁移内容：

- `ids_events`
- `ids_sources`
- `ids_source_sync_attempts`
- `ids_source_package_intakes`
- `ids_source_package_activations`
- 单体 `audit_logs` 中与 IDS 相关的审计记录
- 单体 `users` 中映射后的 IDS 用户
- 上传放行目录、隔离样本目录、审计报告目录、通知与误报学习状态文件

## Docker 启动

容器入口会先自动执行：

```bash
python init_ids_db.py
```

然后启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8170
```

## 健康检查

- 文档：`http://localhost:8170/docs`
- 健康检查：`http://localhost:8170/api/health`
