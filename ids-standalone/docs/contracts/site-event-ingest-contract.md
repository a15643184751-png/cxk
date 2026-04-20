# 网站接入契约：`POST /api/ids/events/ingest`

## 1. 作用

这个接口用于把未来新版网站、站点网关、WAF、日志适配器识别到的安全事件，统一投递到独立 IDS。

推荐用途：

- 网关/WAF 拦截事件
- 站点后端检测到的可疑操作
- 日志适配器解析出的攻击事件
- 外部成熟检测器的标准化结果

不推荐用途：

- 普通业务日志
- 高噪声埋点
- 未经过筛选的全量访问日志

## 2. 鉴权方式

支持两种方式：

### 2.1 IDS 人员 JWT

适合：

- IDS 控制台人工导入事件
- 已登录 IDS 的内部工具

请求头：

```text
Authorization: Bearer <ids-jwt>
```

### 2.2 服务集成令牌

适合：

- 新版网站后端
- 网关日志适配器
- WAF 事件适配器
- 安全采集服务

请求头：

```text
X-IDS-Integration-Token: <shared-token>
X-IDS-Source-System: site-gateway
```

说明：

- `X-IDS-Source-System` 推荐带上调用方名字，便于审计
- 令牌值由后端环境变量 `IDS_INTEGRATION_TOKEN` 控制

## 3. 请求地址

```text
POST /api/ids/events/ingest
Content-Type: application/json
```

## 4. 请求字段

### 4.1 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `event_origin` | 是 | 事件来源类型，允许值：`real` `demo` `test` |
| `source_classification` | 是 | 检测源分类，允许值：`external_mature` `custom_project` `transitional_local` |
| `detector_family` | 是 | 检测器家族，例如 `waf` `gateway` `app` `file` `proxy` |
| `detector_name` | 是 | 检测器名称，例如 `site-gateway` `business-api` |
| `rule_id` | 否 | 外部规则编号 |
| `rule_name` | 否 | 外部规则名称 |
| `source_version` | 否 | 规则版本、策略版本或适配器版本 |
| `source_freshness` | 否 | 数据新鲜度，建议值：`current` `stale` `unknown` |
| `occurred_at` | 是 | 事件发生时间，ISO8601 |
| `client_ip` | 是 | 攻击源 IP |
| `asset_ref` | 否 | 资产标识、接口名或站点资源路径 |
| `attack_type` | 是 | 统一攻击类型，例如 `sql_injection` `xss` `path_traversal` |
| `severity` | 否 | 建议值：`low` `medium` `high` `critical` |
| `confidence` | 是 | 0 到 100 |
| `event_fingerprint` | 条件必填 | 对于 `real` / `demo` 必填；用于去重和关联 |
| `correlation_key` | 否 | 关联键，用于把短时间内相似事件归并 |
| `evidence_summary` | 条件必填 | 当未提供 `raw_evidence` 时必填 |
| `raw_evidence` | 否 | 原始证据摘要对象 |

### 4.2 `raw_evidence` 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `method` | 否 | HTTP 方法 |
| `path` | 否 | 请求路径 |
| `query_snippet` | 否 | 查询串摘要 |
| `body_snippet` | 否 | 请求体摘要 |
| `user_agent` | 否 | UA 摘要 |
| `headers_snippet` | 否 | 请求头摘要 |

## 5. 字段选值建议

### 5.1 `event_origin`

- `real`
  - 真实生产事件
- `demo`
  - 演示事件
- `test`
  - 测试或工具回放事件

未来新版网站正式接入时，生产数据应使用 `real`。

### 5.2 `source_classification`

- `external_mature`
  - 来自成熟外部源，例如 WAF、网关、成熟日志适配器
- `custom_project`
  - 来自你自己网站内部的安全逻辑或专用适配器
- `transitional_local`
  - 过渡期本地规则、临时脚本或过渡检测器

建议：

- 网关 / WAF：`external_mature`
- 网站后端自定义安全判断：`custom_project`

### 5.3 `attack_type`

推荐尽量与当前 IDS 内置命名保持一致，例如：

- `sql_injection`
- `xss`
- `path_traversal`
- `cmd_injection`
- `jndi_injection`
- `scanner`
- `malformed`
- `malware`

## 6. 推荐指纹与关联键策略

### 6.1 `event_fingerprint`

推荐格式：

```text
<client_ip>::<method>::<path>::<attack_type>::<rule_id>
```

示例：

```text
198.51.100.23::POST::/api/order/create::sql_injection::waf-942100
```

### 6.2 `correlation_key`

推荐格式：

```text
<yyyymmddhhmm>::<client_ip>::<attack_type>::<detector_name>
```

示例：

```text
202604151030::198.51.100.23::sql_injection::site-gateway
```

## 7. 推荐请求示例

```json
{
  "event_origin": "real",
  "source_classification": "external_mature",
  "detector_family": "waf",
  "detector_name": "site-gateway",
  "rule_id": "waf-942100",
  "rule_name": "SQL Injection Attack Detected",
  "source_version": "owasp-crs-2026.04",
  "source_freshness": "current",
  "occurred_at": "2026-04-15T10:30:00Z",
  "client_ip": "198.51.100.23",
  "asset_ref": "business-site:/api/order/create",
  "attack_type": "sql_injection",
  "severity": "high",
  "confidence": 88,
  "event_fingerprint": "198.51.100.23::POST::/api/order/create::sql_injection::waf-942100",
  "correlation_key": "202604151030::198.51.100.23::sql_injection::site-gateway",
  "evidence_summary": "WAF blocked a SQL injection payload on the order-create endpoint.",
  "raw_evidence": {
    "method": "POST",
    "path": "/api/order/create",
    "query_snippet": "",
    "body_snippet": "id=1 union select ...",
    "user_agent": "Mozilla/5.0",
    "headers_snippet": "content-type=application/x-www-form-urlencoded"
  }
}
```

## 8. 成功响应

```json
{
  "incident_id": 128,
  "correlation_key": "202604151030::198.51.100.23::sql_injection::site-gateway",
  "linked_event_count": 1,
  "counted_in_real_metrics": true,
  "status": "new"
}
```

字段说明：

- `incident_id`
  - IDS 内部事件 ID
- `correlation_key`
  - 实际落库使用的关联键
- `linked_event_count`
  - 当前事件链上的聚合数量
- `counted_in_real_metrics`
  - 是否计入真实运营指标
- `status`
  - 当前事件状态

## 9. 常见失败响应

### 9.1 鉴权失败

```json
{
  "detail": "Authentication required"
}
```

### 9.2 字段非法

```json
{
  "detail": "Invalid source_classification: invalid_value"
}
```

### 9.3 缺少关键字段

```json
{
  "detail": "detector_family, detector_name, and attack_type are required"
}
```

## 10. 调用位置建议

### 10.1 推荐

- 网关/WAF 日志适配器
- 网站后端安全中间件
- 安全运营辅助脚本

### 10.2 不推荐

- 浏览器前端直接调用
- 无筛选的日志批量直灌

## 11. curl 示例

```bash
curl -X POST "http://127.0.0.1:8170/api/ids/events/ingest" \
  -H "Content-Type: application/json" \
  -H "X-IDS-Integration-Token: your-shared-token" \
  -H "X-IDS-Source-System: site-gateway" \
  -d @event.json
```

## 12. 新版网站接入建议

未来新版网站正式接入时，优先顺序建议是：

1. 先让网关/WAF 能投递阻断事件
2. 再让网站后端投递关键安全事件
3. 最后再补齐高价值审计事件
