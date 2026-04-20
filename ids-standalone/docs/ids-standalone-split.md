# 独立 IDS 拆分说明

## 1. 当前 IDS 依赖了平台哪些东西

### 前端耦合点

- 原单体路由入口还在 [frontend/src/router/routes.ts](/D:/ids/frontend/src/router/routes.ts) 里把 IDS 挂在 `/security/*` 下，依赖平台总布局和菜单。
- 原平台导航和容器壳子来自 [frontend/src/components/layout/AppLayout.vue](/D:/ids/frontend/src/components/layout/AppLayout.vue) 一类公共布局，不是独立 IDS 的壳子。
- 原登录页 [frontend/src/views/login/Login.vue](/D:/ids/frontend/src/views/login/Login.vue) 绑定了供应链角色选择和演示登录逻辑。
- 原 IDS 大页 [frontend/src/views/security/SecurityIDS.vue](/D:/ids/frontend/src/views/security/SecurityIDS.vue) 曾经同时承载事件中心和工作台。

### 后端耦合点

- 原服务入口 [backend/app/main.py](/D:/ids/backend/app/main.py) 同时挂载采购、仓储、配送、告警、溯源和 IDS 全部接口。
- 原鉴权绑定单体用户模型与角色，关键文件是 [backend/app/api/auth.py](/D:/ids/backend/app/api/auth.py)、[backend/app/api/deps.py](/D:/ids/backend/app/api/deps.py)、[backend/app/models/user.py](/D:/ids/backend/app/models/user.py)。
- IDS API 主体在 [backend/app/api/ids.py](/D:/ids/backend/app/api/ids.py)，上传审计在 [backend/app/api/upload.py](/D:/ids/backend/app/api/upload.py)，但之前共用平台用户和路由前缀。
- 上传目录、隔离目录、报告目录和误报学习状态原先跟着单体目录走，典型路径是：
  - [backend/uploads/accepted](/D:/ids/backend/uploads/accepted)
  - [backend/quarantine_uploads](/D:/ids/backend/quarantine_uploads)
  - [backend/upload_reports](/D:/ids/backend/upload_reports)
  - [backend/app/data/ids_operator_state](/D:/ids/backend/app/data/ids_operator_state)

### 数据耦合点

- 单体数据库主源是 [backend/supply_chain.db](/D:/ids/backend/supply_chain.db)，里面同时存在业务表和 IDS 表。
- 原根目录 [supply_chain.db](/D:/ids/supply_chain.db) 不是这次独立迁移的主源。
- 真实 IDS 数据主要在这些表里：
  - `ids_events`
  - `ids_sources`
  - `ids_source_sync_attempts`
  - `ids_source_package_intakes`
  - `ids_source_package_activations`
  - `audit_logs` 里以 `ids_*` 开头的审计记录

## 2. 拆分边界设计

### 采用策略

- 这次不是在原单体里硬拆，而是先复制出 `ids-backend/` 和 `ids-frontend/` 两套独立目录，再逐步瘦身。
- 原因很直接：[frontend/src/views/security/SecurityIDS.vue](/D:/ids/frontend/src/views/security/SecurityIDS.vue) 和 [backend/app/api/ids.py](/D:/ids/backend/app/api/ids.py) 都比较重，直接硬拆会一边改一边断联，风险高于“先复制再削耦合”。

### 当前已落地的边界

- 独立前端目录： [ids-frontend](/D:/ids/ids-frontend)
- 独立后端目录： [ids-backend](/D:/ids/ids-backend)
- 独立后端入口只保留：
  - [ids-backend/app/api/auth.py](/D:/ids/ids-backend/app/api/auth.py)
  - [ids-backend/app/api/ids.py](/D:/ids/ids-backend/app/api/ids.py)
  - [ids-backend/app/api/upload.py](/D:/ids/ids-backend/app/api/upload.py)
- 独立前端只保留 IDS 相关页面与资源：
  - [ids-frontend/src/views/security](/D:/ids/ids-frontend/src/views/security)
  - [ids-frontend/src/views/login](/D:/ids/ids-frontend/src/views/login)
  - [ids-frontend/src/views/overview](/D:/ids/ids-frontend/src/views/overview)
  - [ids-frontend/src/views/notifications](/D:/ids/ids-frontend/src/views/notifications)
  - [ids-frontend/src/api/ids.ts](/D:/ids/ids-frontend/src/api/ids.ts)
  - [ids-frontend/src/api/upload.ts](/D:/ids/ids-frontend/src/api/upload.ts)

### 角色边界

- 独立 IDS 角色已切成：
  - `ids_admin`
  - `ids_operator`
  - `ids_auditor`
  - `ids_viewer`
- 为了兼容旧数据，后端仍把 `system_admin/admin` 映射为 `ids_admin`。

## 3. 前端拆分方案

### 已完成的独立前端结构

- 独立入口： [ids-frontend/src/main.ts](/D:/ids/ids-frontend/src/main.ts)
- 独立应用壳： [ids-frontend/src/App.vue](/D:/ids/ids-frontend/src/App.vue)
- 独立路由： [ids-frontend/src/router/index.ts](/D:/ids/ids-frontend/src/router/index.ts)、[ids-frontend/src/router/routes.ts](/D:/ids/ids-frontend/src/router/routes.ts)
- 独立登录页： [ids-frontend/src/views/login/Login.vue](/D:/ids/ids-frontend/src/views/login/Login.vue)
- 独立首页： [ids-frontend/src/views/overview/IDSOverview.vue](/D:/ids/ids-frontend/src/views/overview/IDSOverview.vue)
- 独立导航壳： [ids-frontend/src/views/security/SecurityCenterLayout.vue](/D:/ids/ids-frontend/src/views/security/SecurityCenterLayout.vue)
- 事件中心： [ids-frontend/src/views/security/SecurityIDS.vue](/D:/ids/ids-frontend/src/views/security/SecurityIDS.vue)
- 分析工作台： [ids-frontend/src/views/security/IDSWorkbench.vue](/D:/ids/ids-frontend/src/views/security/IDSWorkbench.vue)
- 检测工具页： [ids-frontend/src/views/security/IDSDetectionTools.vue](/D:/ids/ids-frontend/src/views/security/IDSDetectionTools.vue)
- 通知配置页： [ids-frontend/src/views/notifications/IDSNotifications.vue](/D:/ids/ids-frontend/src/views/notifications/IDSNotifications.vue)

### 当前路由形态

- `/login`
- `/overview`
- `/events`
- `/workbench`
- `/detection`
- `/notifications`
- `/audit`
- `/situation`
- `/sandbox`

### 前端纠偏结论

- “事件中心”和“分析工作台”已经拆成两页，不再复用同一个主页面。
- “匿名上传”已经退场，检测工具页只保留登录后的“请求攻击检测”和“样本送检”。
- 历史残留的旧公开上传页已经下线，不再作为独立入口保留。

## 4. 后端拆分方案

### 已完成的独立后端结构

- 独立入口： [ids-backend/app/main.py](/D:/ids/ids-backend/app/main.py)
- 运行初始化： [ids-backend/app/bootstrap.py](/D:/ids/ids-backend/app/bootstrap.py)
- 独立鉴权： [ids-backend/app/api/auth.py](/D:/ids/ids-backend/app/api/auth.py)
- 独立角色判断： [ids-backend/app/api/deps.py](/D:/ids/ids-backend/app/api/deps.py)
- 独立配置： [ids-backend/app/config.py](/D:/ids/ids-backend/app/config.py)

### 当前保留的 IDS 能力

- 事件中心接口仍由 [ids-backend/app/api/ids.py](/D:/ids/ids-backend/app/api/ids.py) 提供：
  - 事件列表
  - 筛选
  - 处置
  - 归档
  - 报告导出
- F2 分析工作台相关洞察仍由 [ids-backend/app/api/ids.py](/D:/ids/ids-backend/app/api/ids.py) 和 [ids-backend/app/services/ids_operator_hub.py](/D:/ids/ids-backend/app/services/ids_operator_hub.py) 提供：
  - 攻击画像卡
  - 攻击链时间线
  - 相似事件聚类
  - 误报学习
  - AI 研判
- 样本送检与沙箱链路由 [ids-backend/app/api/upload.py](/D:/ids/ids-backend/app/api/upload.py) 提供。
- 请求攻击检测接口已独立为 `POST /api/ids/request-detect`。
- 通知联动和告警由 [ids-backend/app/services/ids_operator_hub.py](/D:/ids/ids-backend/app/services/ids_operator_hub.py) 提供。

### 数据表边界

- 用户表已切成 `ids_users`，文件见 [ids-backend/app/models/user.py](/D:/ids/ids-backend/app/models/user.py)
- 审计表已切成 `ids_audit_logs`，文件见 [ids-backend/app/models/audit_log.py](/D:/ids/ids-backend/app/models/audit_log.py)
- 事件与规则源表继续沿用 IDS 命名：
  - `ids_events`
  - `ids_sources`
  - `ids_source_sync_attempts`
  - `ids_source_package_intakes`
  - `ids_source_package_activations`

### 运行能力

- 默认数据库：`ids.db`
- 默认管理员自动创建：`ids_admin / 123456`
- 独立健康检查：`/api/health`
- 样本送检接口：`POST /api/upload`
- 请求攻击检测接口：`POST /api/ids/request-detect`
- 上传样本不再通过公开静态目录暴露

### 对“整个 IP / 所有流量都经过 IDS”的真实边界

- 现在这套独立 IDS 已经把应用层请求检测、浏览器路由探测、样本送检审计、规则源同步和告警闭环独立出来了。
- 但它还不能等同于“这个 IP 下所有网段、所有协议、所有端口都被防护”。
- 如果要做到整 IP 全流量接入，下一阶段要把下面这些外部流量源接进 [ids-backend/app/services/ids_ingestion.py](/D:/ids/ids-backend/app/services/ids_ingestion.py) 或新增接入器：
  - 反向代理访问日志
  - WAF / Nginx / OpenResty 拦截日志
  - Suricata / Zeek / NetFlow / 镜像流量检测结果
  - 主机侧 EDR / 防火墙封禁记录

## 5. 数据库 / 文件 / 配置迁移方案

### 已提供的迁移脚本

- 数据库与文件迁移脚本： [ids-backend/scripts/migrate_from_monolith.py](/D:/ids/ids-backend/scripts/migrate_from_monolith.py)
- 数据库初始化脚本： [ids-backend/init_ids_db.py](/D:/ids/ids-backend/init_ids_db.py)

### 需要迁移的数据

- 必迁移：
  - `backend/supply_chain.db` 里的 `ids_events`
  - `ids_sources`
  - `ids_source_sync_attempts`
  - `ids_source_package_intakes`
  - `ids_source_package_activations`
  - `audit_logs` 中 `ids_*` 相关审计记录
  - `users` 中可映射到 IDS 角色的账户
- 必迁移的文件状态：
  - [backend/uploads/accepted](/D:/ids/backend/uploads/accepted)
  - [backend/quarantine_uploads](/D:/ids/backend/quarantine_uploads)
  - [backend/upload_reports](/D:/ids/backend/upload_reports)
  - [backend/app/data/ids_operator_state](/D:/ids/backend/app/data/ids_operator_state)

### 可以重建的数据

- 默认管理员账户可由 [ids-backend/app/bootstrap.py](/D:/ids/ids-backend/app/bootstrap.py) 自动创建
- 前端本地 token、桌面通知授权状态、提示音本地状态都可以重建

### 最小可运行环境清单

- Python 3.12+
- Node 20+
- 后端依赖： [ids-backend/requirements.txt](/D:/ids/ids-backend/requirements.txt)
- 前端依赖： [ids-frontend/package.json](/D:/ids/ids-frontend/package.json)
- 最小环境变量模板： [.env.ids.example](/D:/ids/.env.ids.example)

## 6. 分阶段改造计划

### 阶段 1：先可跑

- 完成独立前端、独立后端、独立登录、独立路由、独立送检与检测工具页。
- 现在这一步已经落到 `ids-frontend/` 和 `ids-backend/` 里。

### 阶段 2：再解耦

- 继续把 [ids-frontend/src/views/security/SecurityIDS.vue](/D:/ids/ids-frontend/src/views/security/SecurityIDS.vue) 按职责拆轻：
  - 事件列表检索与批量处置
  - 规则源管理
  - 通知与桌面告警
- 把 [ids-backend/app/api/ids.py](/D:/ids/ids-backend/app/api/ids.py) 再拆成：
  - `events`
  - `sources`
  - `notifications`
  - `reports`
  - `analytics`

### 阶段 3：独立部署

- 现已提供前端镜像、后端镜像和 Compose：
  - [ids-frontend/Dockerfile](/D:/ids/ids-frontend/Dockerfile)
  - [ids-frontend/nginx.conf](/D:/ids/ids-frontend/nginx.conf)
  - [docker-compose.ids.yml](/D:/ids/docker-compose.ids.yml)
- 本地开发建议：
  - 前端 `5175`
  - 后端 `8170`
- 测试 / 预生产建议：
  - 优先 Docker 化，数据卷单独挂 `ids-data`
- 生产建议：
  - 先以容器方式单独上一个 IDS 子系统
  - 再把代理/WAF/Suricata/Zeek 等流量源接入

## 7. 第一阶段应该直接修改哪些文件

### 已直接修改的新独立后端文件

- [ids-backend/app/config.py](/D:/ids/ids-backend/app/config.py)
- [ids-backend/app/bootstrap.py](/D:/ids/ids-backend/app/bootstrap.py)
- [ids-backend/app/main.py](/D:/ids/ids-backend/app/main.py)
- [ids-backend/app/api/auth.py](/D:/ids/ids-backend/app/api/auth.py)
- [ids-backend/app/api/deps.py](/D:/ids/ids-backend/app/api/deps.py)
- [ids-backend/app/api/ids.py](/D:/ids/ids-backend/app/api/ids.py)
- [ids-backend/app/api/upload.py](/D:/ids/ids-backend/app/api/upload.py)
- [ids-backend/app/services/ids_operator_hub.py](/D:/ids/ids-backend/app/services/ids_operator_hub.py)
- [ids-backend/app/services/upload_ai_audit.py](/D:/ids/ids-backend/app/services/upload_ai_audit.py)
- [ids-backend/app/services/ids_engine.py](/D:/ids/ids-backend/app/services/ids_engine.py)
- [ids-backend/init_ids_db.py](/D:/ids/ids-backend/init_ids_db.py)
- [ids-backend/scripts/migrate_from_monolith.py](/D:/ids/ids-backend/scripts/migrate_from_monolith.py)
- [ids-backend/docker-entrypoint.sh](/D:/ids/ids-backend/docker-entrypoint.sh)
- [ids-backend/Dockerfile](/D:/ids/ids-backend/Dockerfile)

### 已直接修改的新独立前端文件

- [ids-frontend/vite.config.ts](/D:/ids/ids-frontend/vite.config.ts)
- [ids-frontend/src/main.ts](/D:/ids/ids-frontend/src/main.ts)
- [ids-frontend/src/App.vue](/D:/ids/ids-frontend/src/App.vue)
- [ids-frontend/src/api/request.ts](/D:/ids/ids-frontend/src/api/request.ts)
- [ids-frontend/src/api/auth.ts](/D:/ids/ids-frontend/src/api/auth.ts)
- [ids-frontend/src/api/ids.ts](/D:/ids/ids-frontend/src/api/ids.ts)
- [ids-frontend/src/api/upload.ts](/D:/ids/ids-frontend/src/api/upload.ts)
- [ids-frontend/src/stores/user.ts](/D:/ids/ids-frontend/src/stores/user.ts)
- [ids-frontend/src/router/index.ts](/D:/ids/ids-frontend/src/router/index.ts)
- [ids-frontend/src/router/routes.ts](/D:/ids/ids-frontend/src/router/routes.ts)
- [ids-frontend/src/types/role.ts](/D:/ids/ids-frontend/src/types/role.ts)
- [ids-frontend/src/views/login/Login.vue](/D:/ids/ids-frontend/src/views/login/Login.vue)
- [ids-frontend/src/views/overview/IDSOverview.vue](/D:/ids/ids-frontend/src/views/overview/IDSOverview.vue)
- [ids-frontend/src/views/notifications/IDSNotifications.vue](/D:/ids/ids-frontend/src/views/notifications/IDSNotifications.vue)
- [ids-frontend/src/views/security/SecurityCenterLayout.vue](/D:/ids/ids-frontend/src/views/security/SecurityCenterLayout.vue)
- [ids-frontend/src/views/security/IDSWorkbench.vue](/D:/ids/ids-frontend/src/views/security/IDSWorkbench.vue)
- [ids-frontend/src/views/security/IDSDetectionTools.vue](/D:/ids/ids-frontend/src/views/security/IDSDetectionTools.vue)
- [ids-frontend/src/views/security/SecurityIDS.vue](/D:/ids/ids-frontend/src/views/security/SecurityIDS.vue)
- [ids-frontend/src/views/security/SecurityLogAudit.vue](/D:/ids/ids-frontend/src/views/security/SecurityLogAudit.vue)
- [ids-frontend/src/views/security/SecuritySandbox.vue](/D:/ids/ids-frontend/src/views/security/SecuritySandbox.vue)
- [ids-frontend/src/views/security/SecuritySituation.vue](/D:/ids/ids-frontend/src/views/security/SecuritySituation.vue)
- [ids-frontend/src/views/error/SecurityBlocked.vue](/D:/ids/ids-frontend/src/views/error/SecurityBlocked.vue)

### 已补充的部署与启动文件

- [ids-frontend/Dockerfile](/D:/ids/ids-frontend/Dockerfile)
- [ids-frontend/nginx.conf](/D:/ids/ids-frontend/nginx.conf)
- [docker-compose.ids.yml](/D:/ids/docker-compose.ids.yml)
- [.env.ids.example](/D:/ids/.env.ids.example)
- [start-ids.bat](/D:/ids/start-ids.bat)
- [start-ids-ai.bat](/D:/ids/start-ids-ai.bat)
- [start-ids.ps1](/D:/ids/start-ids.ps1)
