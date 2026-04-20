# 网站接入契约：`POST /api/upload`

## 1. 作用

这个接口用于把未来新版网站里的文件上传，统一送到独立 IDS 做静态检测、AI 审计、隔离和报告生成。

它适合的定位是：

- 全站统一文件扫描服务
- 业务站上传的唯一安全判定入口

## 2. 鉴权方式

支持两种方式：

### 2.1 IDS 人员 JWT

适合：

- IDS 控制台内部送检
- 人工样本复核

### 2.2 服务集成令牌

适合：

- 新版网站后端
- 统一上传网关
- 后台任务服务

推荐请求头：

```text
X-IDS-Integration-Token: <shared-token>
X-IDS-Source-System: business-site-upload
```

## 3. 强烈推荐的调用方式

推荐：

- 新版网站后端收到上传后，服务端再调用 IDS

不推荐：

- 浏览器直接调用独立 IDS 上传接口

原因：

- 业务站通常还需要保留自己的业务上下文
- 服务端调用更容易补充业务主键、操作人和审计信息
- 以后更方便做失败重试和灰度切换

## 4. 请求地址

```text
POST /api/upload
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `file` | 是 | 上传文件本体 |

## 5. 成功响应：放行

```json
{
  "ok": true,
  "filename": "purchase-order.xlsx",
  "saved_as": "8a91c123_purchase-order.xlsx",
  "size": 24813,
  "url": null,
  "upload_state": "accepted",
  "quarantined": false,
  "stored_in": "accepted",
  "audit": {
    "verdict": "pass",
    "risk_level": "low",
    "confidence": 64,
    "summary": "The file passed static upload checks.",
    "analysis_mode": "static_only",
    "analysis_mode_label": "Static audit",
    "provider": "static-rules",
    "llm_used": false,
    "ai_available": false,
    "recommended_actions": [
      "Allow the file into the internal sample store."
    ]
  }
}
```

业务站建议处理：

- 允许后续业务保存
- 记录 `saved_as`
- 记录 `audit.verdict` / `audit.risk_level`

## 6. 成功响应：隔离

```json
{
  "ok": true,
  "filename": "shell.php",
  "saved_as": "41c0a822_shell.php",
  "size": 1732,
  "url": null,
  "upload_state": "quarantined",
  "quarantined": true,
  "stored_in": "quarantine",
  "audit": {
    "verdict": "quarantine",
    "risk_level": "high",
    "confidence": 88,
    "summary": "The file matched high-risk execution traits.",
    "analysis_mode": "static_only",
    "analysis_mode_label": "Static audit",
    "provider": "static-rules",
    "llm_used": false,
    "ai_available": false,
    "linked_event_id": 132,
    "recommended_actions": [
      "Keep the file in quarantine.",
      "Review in the IDS sandbox."
    ]
  },
  "security_alert": {
    "style": "ids_quarantine",
    "http_status_hint": 403,
    "title": "Sample submission failed security review",
    "message": "The file matched high-risk execution traits.",
    "detail": "The sample was placed into quarantine."
  }
}
```

业务站建议处理：

- 拒绝业务侧继续保存
- 给用户返回“上传未通过安全审计”
- 把 `saved_as` 和 `linked_event_id` 记入业务审计

## 7. 常见失败响应

### 7.1 鉴权失败

```json
{
  "detail": "Authentication required"
}
```

### 7.2 文件名非法

```json
{
  "detail": "Invalid filename"
}
```

### 7.3 AI 审计配置错误或上游不可用

```json
{
  "detail": "..."
}
```

HTTP 状态：

- `503`

业务站建议处理：

- 不要默默放行
- 应该视为“审计失败，暂不接收”

## 8. 审计字段建议保留

业务站在自己的数据库里，建议至少保留这些字段：

- `ids_saved_as`
- `ids_upload_state`
- `ids_quarantined`
- `ids_audit_verdict`
- `ids_audit_risk_level`
- `ids_audit_confidence`
- `ids_linked_event_id`
- `ids_scan_at`

## 9. 推荐接入顺序

### 9.1 第一期

- 只接最重要的上传入口
- 管理后台附件
- 文档导入
- 富文本图片/附件

### 9.2 第二期

- 业务单据附件
- 压缩包导入
- 模板导入
- 报表上传

## 10. 服务端调用示例

```bash
curl -X POST "http://127.0.0.1:8170/api/upload" \
  -H "X-IDS-Integration-Token: your-shared-token" \
  -H "X-IDS-Source-System: business-site-upload" \
  -F "file=@purchase-order.xlsx"
```

## 11. 网站侧处理建议

### 11.1 通过

- 写业务记录
- 保存业务附件关系

### 11.2 隔离

- 拒绝落业务库
- 告知用户文件未通过安全审计
- 将 `saved_as` 和 `linked_event_id` 记入安全审计

### 11.3 审计失败

- 返回“上传审核服务暂不可用”
- 不自动降级为放行

## 12. 推荐补充动作

当业务站调用上传扫描接口后，建议同时向自己的业务审计表记录：

- 上传人
- 业务单据 ID
- 原文件名
- IDS 决策
- IDS 事件 ID
- 调用时间
