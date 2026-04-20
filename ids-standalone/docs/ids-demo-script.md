# IDS 演示脚本

## 演示目标

走一条现在真实可用的 IDS 链路：

1. 登录 IDS。
2. 在“检测工具”里做请求攻击检测和样本送检。
3. 高危样本会进入沙箱并生成 IDS 事件。
4. 事件中心、分析工作台、沙箱、审计中心可以互相跳转核验。
5. 配好模型密钥后，可以在事件与样本链路里看到真实 AI 审计/研判。

## 启动方式

- 一键静默启动：`start-ids.bat`
- 一键交互式 AI 启动：`start-ids-ai.bat`
- 启动后地址：
  - 前端：`http://127.0.0.1:5175`
  - 后端：`http://127.0.0.1:8170`
  - 自动登录：`http://127.0.0.1:5175/login?autologin=1`
- 默认管理员：`ids_admin / 123456`

## 必开页面

- `/login?autologin=1`
- `/events`
- `/workbench`
- `/detection`
- `/sandbox`
- `/audit`
- `/situation`

## 演示材料

- 正常文件：`tmp/codex-note.txt`
- 恶意文件：`tmp/codex-webshell.php`

## 场景 1：确认 AI 审计模式

- 打开 `http://127.0.0.1:8170/api/health`
- 看 `ids_upload_audit_mode`
- 预期：
  - 未配密钥时是 `static_only`
  - 配密钥后是 `llm_assisted`

## 场景 2：请求攻击检测

- 登录后打开 `/detection`
- 在“请求攻击检测”输入恶意 query 或 body
- 点击“开始检测”
- 预期：
  - 页面显示是否命中规则、风险分、是否会拦截
  - 若命中，会生成事件，可直接跳到事件中心和工作台

## 场景 3：样本送检

- 在 `/detection` 选择 `tmp/codex-note.txt`
- 点击“提交送检”
- 预期：
  - 低风险样本送检通过
  - 不再出现匿名上传、公开访问地址之类旧语义

- 再上传 `tmp/codex-webshell.php`
- 预期：
  - 样本被隔离到沙箱
  - 同步生成 IDS 事件
  - 高危事件会触发 IDS 预警

## 场景 4：事件中心与工作台分离

- 打开 `/events`
- 确认这里只做事件列表、筛选、处置、归档

- 再打开 `/workbench`
- 确认这里只做：
  - 攻击画像卡
  - AI 研判
  - 攻击链时间线
  - 相似事件聚类
  - 误报学习
  - 规则链与请求包查看
  - 报告导出

## 场景 5：沙箱与审计闭环

- 打开 `/sandbox`
- 找到刚才被隔离的样本
- 查看报告或重新分析
- 再打开 `/audit`
- 搜索：
  - `ids_sample_submit_quarantine`
  - `ids_sample_submit_release`
  - `ids_sandbox_analyze`
- 预期：
  - 样本、事件、审计三条线能互相对上

## 演示话术边界

- 这套独立 IDS 现在已经独立登录、独立事件闭环、独立告警、独立审计。
- 它当前能防护的是“已经接进 IDS 的流量和样本”。
- 如果要做到“整个 IP 下所有网段、所有协议、所有端口都经过 IDS”，下一阶段要把代理/WAF/Suricata/Zeek/NetFlow/防火墙日志接入采集链路。
