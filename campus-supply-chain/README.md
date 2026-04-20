# 校园物资供应链安全健康监测平台

采购 → 仓储 → 配送 → 溯源 → 预警 → AI 智能体

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus + Pinia + TypeScript |
| 后端 | FastAPI + SQLAlchemy + JWT |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| 智能体 | 规则引擎 + 可选 LLM（Ollama / OpenAI 兼容 / **DeepSeek**） |

## 快速启动

### 1. 后端

Windows 可双击或命令行运行 `backend/start.bat`：选择本机/全网访问、按需输入 API Key 后启动。

```bash
cd backend
pip install -r requirements.txt
python init_db.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8166
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

### 3. 访问

- 前端：http://localhost:5173
- 后端文档：http://localhost:8166/docs

### 预置账号（开发环境）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| logistics_admin | 123456 | 后勤管理员 |
| warehouse_procurement | 123456 | 仓储采购员 |
| campus_supplier | 123456 | 校园合作供应商 |
| counselor_teacher | 123456 | 辅导员教师 |

角色职责与权限见：`docs/角色与权限交互矩阵.md`

### AI 智能体（教师「小链」）

- 教师 **智能工作台** 与部分角色对话走 `/ai/chat`，支持多轮会话与 **Function Calling**（库存、目录、预警、拟申请清单、确认后建单等）。
- 在 `backend/.env` 中配置 DeepSeek（示例）后重启后端：

```env
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的_API_Key
LLM_MODEL=deepseek-chat
```

- 未配置大模型时，仍可使用规则引擎（例如「现在什么物资可能短缺？」）。
- 可选：将 `LLM_PROVIDER=ollama` 且 `LLM_BASE_URL=http://127.0.0.1:11434` 使用本地 Ollama（工具调用能力依模型而定）。

### 发布到 GitHub / 开源前检查

- **不要提交** `backend/.env`、任何含 `API_KEY` / `SECRET_KEY` 的本地文件（仓库已 `.gitignore`）。
- 若曾在本地填过真实 **LLM / JWT 密钥**，推送前请确认未进入 Git 历史；如已误传，请在服务商**轮换密钥**并考虑 `git filter-repo` 清理历史。
- 预置账号密码 `123456` 仅用于开发环境，**生产环境务必修改**并收紧访问控制。

## Docker 发布与一键拉取

### 1) 发布到你的 Docker 仓库（Docker Hub）

你的仓库：`guqijin/campussupplychainsecurityplatform`

在项目根目录执行（PowerShell）：

```powershell
docker login
.\scripts\push-docker.ps1 -DockerUser "guqijin" -RepoName "campussupplychainsecurityplatform" -Tag "latest"
```

会推送两个镜像标签到同一仓库：

- `guqijin/campussupplychainsecurityplatform:backend-latest`
- `guqijin/campussupplychainsecurityplatform:frontend-latest`

### 1.1) 推荐：使用 GitHub Actions 自动发布（方案 B）

仓库已内置工作流：`.github/workflows/docker-publish.yml`

- 触发条件：
  - push 到 `main` / `master`
  - push 标签 `v*`（例如 `v1.0.0`）
  - 手动触发 `workflow_dispatch`
- 推送镜像：
  - 常规：`guqijin/campussupplychainsecurityplatform:backend-latest`、`frontend-latest`
  - 打标签发布（如 `v1.0.0`）时额外推送：`backend-v1.0.0`、`frontend-v1.0.0`

首次使用需在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 添加：

- `DOCKERHUB_USERNAME`：`guqijin`
- `DOCKERHUB_TOKEN`：Docker Hub Access Token（不是密码）

### 2) 给别人一键拉取运行（无需本地构建）

对方只需要拿到 `docker-compose.pull.yml`，然后执行：

```bash
docker compose -f docker-compose.pull.yml up -d
```

默认访问地址：`http://<服务器IP>:8080`

### 3) 可选：部署时配置密钥

在 `docker-compose.pull.yml` 同目录创建 `.env`（不要提交到仓库）：

```env
SECRET_KEY=请改成随机长字符串
IDS_AI_ANALYSIS=false
LLM_PROVIDER=ollama
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=qwen2:7b
```
