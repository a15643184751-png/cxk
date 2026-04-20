# IDS 与网站服务启动说明

## 1. 目录位置

- 工作目录：`D:\ids`
- 供应链项目：`D:\ids\gongyinglian\workspace\CampusSupplyChainSecurityPlatform`
- IDS 项目：`D:\ids\ids-standalone`

## 2. 启动前先确认

如果你要跑的是“双机模式”，也就是：

- IDS 在机器 A
- 网站在机器 B

那么先做这两件事：

1. 在 IDS 机器上把 `D:\ids\ids-standalone\ids-backend\.env` 配成网站机器的真实地址和端口
2. 确认网站机器上的两个网站已经能被 IDS 机器访问到

建议先执行配置脚本：

```bat
D:\ids\runtime\startup\configure-ids-multisite.bat
```

双机两站点的具体填写方式，看这个文件：

`D:\ids\docs\IDS_MULTI_SITE_MANUAL_CONFIG.md`

## 3. 网站机器怎么启动

网站机器负责启动业务站点本身，IDS 机器不代替网站机器启动这些站点。

### 3.1 网站 1 是当前供应链项目

后端：

```powershell
cd D:\ids\gongyinglian\workspace\CampusSupplyChainSecurityPlatform\backend
D:\ids\runtime\venvs\campus-backend\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8166
```

前端：

```powershell
cd D:\ids\gongyinglian\workspace\CampusSupplyChainSecurityPlatform\frontend
npm.cmd run dev -- --host 0.0.0.0 --port 5173
```

### 3.2 网站 2 是另一套业务系统

网站 2 不要求一定是当前仓库里的项目，只要它能在网站机器上正常启动，并且你把真实地址填进 IDS 即可。

如果网站 2 也是前后端分离，就按它自己的真实命令启动，并确保端口与 `.env` 一致，例如：

```text
前端: 5273
后端: 8266
```

如果网站 2 是单体服务，就只要确保这个单体服务能正常监听，例如：

```text
http://10.134.32.132:8080
```

然后在 IDS 配置里把它的前后端上游都写成这个地址。

## 4. IDS 机器怎么启动

### 4.1 推荐方式

在 IDS 机器执行：

```bat
D:\ids\start-campus-ids.bat -ForceRestart
```

这个脚本已经支持双机模式：

- 如果 `.env` 里的上游地址是远程网站机器 IP，脚本只启动 IDS 服务
- 不会在 IDS 机器上强行拉起本地供应链服务
- 会根据 `IDS_GATEWAY_DEFAULT_PORT` 和 `IDS_GATEWAY_PORT_MAP` 自动启动多个入口网关

### 4.2 手工分开启动

如果你想分开看每个进程，也可以按下面顺序单独启动。

IDS 后端：

```powershell
cd D:\ids\ids-standalone\ids-backend
D:\ids\runtime\venvs\ids-backend\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8170
```

IDS 前端：

```powershell
cd D:\ids\ids-standalone\ids-frontend
npm.cmd run dev -- --host 0.0.0.0 --port 5175
```

默认站点网关：

```powershell
cd D:\ids\ids-standalone\ids-backend
D:\ids\runtime\venvs\ids-backend\Scripts\python.exe -m uvicorn app.gateway_main:app --host 0.0.0.0 --port 8188
```

第二站点网关：

```powershell
cd D:\ids\ids-standalone\ids-backend
D:\ids\runtime\venvs\ids-backend\Scripts\python.exe -m uvicorn app.gateway_main:app --host 0.0.0.0 --port 8288
```

如果你在 `IDS_GATEWAY_PORT_MAP` 里又加了更多入口，就按对应端口继续启动。

## 5. 双机示例

如果你的环境是：

- IDS 机器：`10.134.32.142`
- 网站机器：`10.134.32.132`
- 网站 1：`5173 / 8166`
- 网站 2：`5273 / 8266`

那么启动后访问地址应该是：

- 网站 1：`http://10.134.32.142:8188`
- 网站 2：`http://10.134.32.142:8288`
- IDS 控制台：`http://10.134.32.142:5175`

## 6. 启动后检查

### 6.1 检查 IDS 机器端口

```powershell
netstat -ano | Select-String ':5175|:8170|:8188|:8288'
```

### 6.2 检查网站机器端口

```powershell
netstat -ano | Select-String ':5173|:8166|:5273|:8266'
```

### 6.3 检查健康状态

在 IDS 机器检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8170/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8188/gateway/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8288/gateway/health
```

如果第二个网站是单体服务，没有单独后端健康接口，网关健康接口正常即可。

## 7. 验证是否真的经过 IDS

### 7.1 正常访问

在任意客户端访问：

```text
http://10.134.32.142:8188
http://10.134.32.142:8288
```

### 7.2 验证拦截

在任意客户端访问：

```text
http://10.134.32.142:8188/?id=1%20union%20select%201
```

或者：

```text
http://10.134.32.142:8288/?id=1%20union%20select%201
```

预期结果：

- 浏览器收到 `403`
- IDS 会话记录里能看到真实来源 IP
- IDS 事件中心出现对应攻击类型

### 7.3 验证封禁 IP

先在 IDS 后端登录拿令牌：

```powershell
$login = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8170/api/auth/login' -ContentType 'application/json' -Body '{"username":"ids_admin","password":"123456"}'
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
```

封禁某个来源 IP，例如 `10.134.32.197`：

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8170/api/traffic/blocklist' -Headers $headers -ContentType 'application/json' -Body '{"ip":"10.134.32.197","note":"manual_block"}'
```

之后这个 IP 再访问：

- `http://10.134.32.142:8188`
- `http://10.134.32.142:8288`

都会收到 `403`。

解除封禁：

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8170/api/traffic/blocklist/remove' -Headers $headers -ContentType 'application/json' -Body '{"ip":"10.134.32.197"}'
```

## 8. 防绕过的关键点

如果网站机器的业务端口仍然对所有来源开放，那么别人仍然可以绕过 IDS，直接访问网站机器。

所以要保证：

- 客户端只访问 IDS 机器
- 网站机器业务端口只允许来自 IDS 机器 IP 的访问

如果不做这一步，IDS 仍然能工作，但只能防“经过 IDS 的流量”，无法防“绕过 IDS 的直连流量”。

## 9. 停止服务

先查看端口占用：

```powershell
netstat -ano | Select-String ':5173|:5175|:8166|:8170|:8188|:8288'
```

然后按 PID 停止：

```powershell
taskkill /PID <PID> /F
```

## 10. 当前这套脚本已经能处理什么

目前脚本已经支持：

- IDS 本机模式
- IDS 远程代理网站机器模式
- 多入口端口映射多个网站
- 自动读取 `.env` 启动多个网关入口
- 根据上游地址是否为远程 IP，决定是否跳过本地供应链服务启动
