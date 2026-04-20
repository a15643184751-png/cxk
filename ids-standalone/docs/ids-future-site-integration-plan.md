# 旧站参考版 -> 未来新版网站 接入边界清单

## 1. 当前判断

你手里的站点是“添加前的网站”，不是最终要对接的“添加后的网站”。

所以这个旧站现在只能承担两个作用：

- 帮我们识别原来网站有哪些登录、上传、审计、事件链路
- 帮我们提前把独立 IDS 的稳定接入边界做出来

它不能承担的作用是：

- 作为未来新版网站的最终接口标准
- 作为未来业务结构、路由结构、上传链路的可靠依据

结论很明确：

独立 IDS 现在要做的是“接口先稳定、边界先收口”，而不是继续深耦合旧站内部实现。

## 1.1 当前已落地的接入能力

截至这轮整理，独立 IDS 已经具备下面两项可直接用于未来新版网站的服务对服务接入能力：

- `POST /api/upload`
  - 已支持通过 `X-IDS-Integration-Token` 调用
- `POST /api/ids/events/ingest`
  - 已支持通过 `X-IDS-Integration-Token` 调用

推荐附带：

- `X-IDS-Source-System`

对应配置项：

- `IDS_INTEGRATION_TOKEN`

## 2. 推荐接入原则

对未来新版网站，推荐只保留 4 个稳定接入边界：

1. 统一入口边界
   - 网站请求先经过网关 / 反向代理 / WAF
   - IDS 不直接绑定每个业务页面

2. 文件上传边界
   - 全站上传统一走扫描接口
   - 不允许每个业务模块各自实现安全判断

3. 安全事件边界
   - 网站、网关、WAF、日志适配器统一把安全事件投递给 IDS
   - 不依赖站内页面结构

4. 审计回传边界
   - 关键业务动作可选回传到 IDS
   - 只传审计事实，不传整套业务耦合逻辑

这 4 个边界稳定以后，就算新版网站新增很多内容，影响也主要落在适配层，而不是落在 IDS 主体。

## 3. 现在这套独立 IDS 已经具备的稳定边界

基于现有代码，下面这些可以视为“独立 IDS 对外可保留的稳定能力”。

### 3.1 认证边界

- `POST /api/auth/login`
- `GET /api/auth/info`
- `GET /api/auth/users`
- `POST /api/auth/users`

适合的定位：

- 当前独立 IDS 自己维护操作员账号
- 未来可改成对接新版网站 SSO，但现在不建议先绑死

### 3.2 文件扫描边界

- `POST /api/upload`
- `GET /api/upload/quarantine`
- `POST /api/upload/quarantine/analyze`
- `GET /api/upload/quarantine/{filename}/report`

适合的定位：

- 作为“全站统一文件扫描服务”
- 新版网站以后无论增加多少上传页面，都应统一接到这里

### 3.3 事件接收边界

- `POST /api/ids/events/ingest`

适合的定位：

- 接收来自网关、WAF、日志适配器、业务站点的标准化安全事件
- 这是未来新版网站最值得优先依赖的接口之一

### 3.4 安全运营边界

- `GET /api/ids/events`
- `GET /api/ids/events/{event_id}`
- `GET /api/ids/events/{event_id}/insight`
- `GET /api/ids/events/{event_id}/report`
- `PUT /api/ids/events/{event_id}/archive`
- `PUT /api/ids/events/{event_id}/status`
- `POST /api/ids/events/{event_id}/analyze`
- `POST /api/ids/events/{event_id}/block`
- `POST /api/ids/events/{event_id}/unblock`
- `POST /api/ids/events/{event_id}/dispatch-notifications`

适合的定位：

- 事件研判、处置、封禁、通知分发
- 这些能力应继续保留在 IDS 内，不应该回塞到业务站

### 3.5 规则与检测源边界

- `GET /api/ids/sources`
- `POST /api/ids/sources`
- `PUT /api/ids/sources/{source_id}`
- `POST /api/ids/sources/{source_id}/sync`
- `POST /api/ids/source-packages/preview`
- `POST /api/ids/source-packages/activate`
- `GET /api/ids/source-packages`

适合的定位：

- 由 IDS 独立管理规则源和激活包
- 不让业务站决定检测规则细节

## 4. 哪些事情现在就能先做

下面这些不依赖“新版网站已经到手”，现在就可以推进。

### 4.1 把独立 IDS 的对接方式固定下来

推荐固定成：

- 网站前置网关 / WAF
- 网站上传统一转发到 IDS 扫描
- 网站或日志适配器把安全事件投递到 `POST /api/ids/events/ingest`
- IDS 自己负责事件中心、研判、告警、封禁

也就是说，现在就确定“接入方式”，不要等新版网站出来后再临时拍脑袋。

### 4.2 定义标准化事件模型

`/api/ids/events/ingest` 应该成为未来各类外部来源的统一落点。  
现在就可以先把标准字段定下来。

建议至少统一这些字段：

- `event_origin`
- `source_classification`
- `detector_family`
- `detector_name`
- `attack_type`
- `client_ip`
- `occurred_at`
- `severity`
- `confidence`
- `rule_id`
- `rule_name`
- `event_fingerprint`
- `correlation_key`
- `evidence_summary`
- `raw_evidence`

建议的最小接入示例：

```json
{
  "event_origin": "real",
  "source_classification": "external_mature",
  "detector_family": "waf",
  "detector_name": "site-gateway",
  "attack_type": "sql_injection",
  "client_ip": "198.51.100.23",
  "severity": "high",
  "confidence": 88,
  "rule_id": "waf-942100",
  "rule_name": "SQL Injection Attack Detected",
  "source_version": "2026-04-15",
  "source_freshness": "current",
  "event_fingerprint": "198.51.100.23::POST::/api/order/create::sql_injection::waf-942100",
  "correlation_key": "202604151030::198.51.100.23::sql_injection::site-gateway",
  "evidence_summary": "WAF blocked a SQL injection payload on the order-create endpoint.",
  "raw_evidence": {
    "method": "POST",
    "path": "/api/order/create",
    "query_snippet": "",
    "body_snippet": "id=1 union select ...",
    "headers_snippet": "content-type=application/x-www-form-urlencoded",
    "user_agent": "Mozilla/5.0"
  }
}
```

### 4.3 定义全站文件上传接入方式

现在就应该定死一条规则：

- 新版网站里凡是文件上传，都统一走 IDS 扫描入口
- 业务站不自己做“是否危险”的最终判断

推荐调用路径：

- 业务站或上传网关调用 `POST /api/upload`
- 返回结果区分：
  - `accepted`
  - `quarantined`
  - `review`

### 4.4 定义网站审计回传范围

现在就可以先把“哪些操作值得回传给 IDS”定下来。

建议先回传这几类：

- 登录失败 / 频繁登录失败
- 账号提权 / 权限变更
- 文件上传 / 下载关键动作
- 后台管理敏感操作
- 新增外部链接、脚本、富文本内容发布
- 高危配置修改

注意：

这里只回传“审计事件”，不要把整个业务流程嵌进 IDS。

### 4.5 明确部署边界

现在就应该确定未来目标形态：

- `site-gateway`
- `business-site`
- `ids-frontend`
- `ids-api`
- `ids-worker`（后续）

不要再让业务站和 IDS 共用一个前端壳、一个后端入口、一个数据库。

## 5. 哪些事情必须等新版网站出来后再接

下面这些内容，如果新版网站还没拿到，就不值得现在硬做。

### 5.1 登录对接方式

需要等新版网站确认：

- 继续独立登录
- 统一 SSO
- 业务站 JWT 互信
- 反向代理层单点登录

现在不要先把 IDS 登录强耦合到旧站用户表。

### 5.2 上传入口清单

必须等新版网站确认：

- 有多少上传页面
- 上传是前端直传还是后端中转
- 是否有分片上传
- 是否有富文本图片上传
- 是否有导入 Excel / ZIP / PDF 等特殊入口

### 5.3 网站真实入口位置

必须等新版网站确认：

- 是否有统一 Nginx / APISIX / OpenResty
- 是否经过 CDN
- 是否有对象存储直传
- 是否存在内网接口绕过网关

如果这些不清楚，就没法保证“全站都经过 IDS 前置入口”。

### 5.4 新版网站新增模块的风险点

必须等新版网站确认：

- 新增了哪些业务模块
- 哪些模块会执行富文本、脚本、模板、导入导出、附件解析
- 哪些模块有管理端操作
- 哪些接口暴露公网

这些都属于“新版业务风险面”，旧站无法可靠代表。

### 5.5 精确审计点

必须等新版网站确认：

- 哪些动作要记为安全审计
- 需要带哪些业务主键
- 审计落点放在哪一层

旧站能给你灵感，但不能直接照搬。

## 6. 推荐的对接模式

### 模式 A：最推荐

网关 + 上传扫描 + 事件回传 + IDS 独立控制台

特点：

- 和未来新版网站耦合最小
- 对网站新增页面和模块最稳
- 返工最少

### 模式 B：中等耦合

业务站登录与 IDS 做账号打通，其他仍保持独立

特点：

- 用户体验更统一
- 但需要等新版网站身份体系稳定后再做

### 模式 C：不推荐

把 IDS 重新嵌回业务站前后端内部

特点：

- 初看接得快
- 后期每次业务站结构变化都要返工

## 7. 第一阶段实施顺序

下面这个顺序适合你现在马上开始。

### 第 1 步：固定独立 IDS 的“外部接入边界”

先以文档和接口约定的方式固定：

- 文件扫描入口
- 事件接收入口
- 审计回传入口
- 独立控制台

### 第 2 步：把旧站当样本，整理接入点

从旧站只提取：

- 登录链路参考
- 上传链路参考
- 审计点参考
- 反向代理 / API 入口参考

不要继续按旧站内部模块深挖实现。

### 第 3 步：为新版网站准备适配层

未来新版网站出来后，只做这几类适配：

- 网关接入
- 上传接入
- 审计回传接入
- 可选登录打通

### 第 4 步：等新版网站到手后补最后一公里

到那时再确认：

- 新增模块
- 新上传入口
- 新公网接口
- 新管理后台
- 新部署入口

## 8. 给你的一句落地建议

现在不要继续问“旧站每个接口怎么改才能兼容未来新版”。

现在真正该做的是：

把独立 IDS 先做成一个对新版网站友好的“站外安全能力平台”，只暴露稳定接入边界，等新版网站来了再接适配层。

这条路返工最少，也最符合你目前手里只有“添加前网站”的现实。

## 9. 下一轮最具体的工作项

如果继续往下做，下一轮建议直接进入这三件事：

1. 列出旧站中的上传入口、登录入口、后台敏感入口参考清单
2. 把 IDS 的“事件接收”和“上传扫描”整理成对接契约文档
3. 设计新版网站的网关接入草图

这三件事都可以在新版网站还没到手前先完成。
