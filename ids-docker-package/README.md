# IDS Docker Package

这个目录现在只保留一个对外入口：`start-ids-docker.*`。

- `start-ids-docker.ps1` / `start-ids-docker.sh`
  统一部署入口。负责收集关键参数、生成运行配置、生成 Compose，并根据你的选择执行本地构建或镜像仓库部署。
- `start-ids-docker.bat`
  Windows 包装器，双击即可调用 `start-ids-docker.ps1`。

其余部署脚本已经收进 `internal/`，不再散落在包根目录。

## 推荐入口

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start-ids-docker.ps1
```

或者双击：

```text
start-ids-docker.bat
```

### Linux

```bash
chmod +x ./start-ids-docker.sh
./start-ids-docker.sh
```

## 目录结构

- `ids-backend/`：IDS 后端与网关镜像构建目录
- `ids-frontend/`：IDS 前端镜像构建目录
- `config/`：运行脚本生成的后端环境配置
- `ids-data/`：持久化数据目录
- `internal/`：内部部署实现，不再作为日常手工入口
- `docs/`：部署说明和辅助文档

## 真实生效的配置

部署脚本和前端通信配置中心里，真正影响运行结果的是这些：

- IDS 控制台端口
- IDS API 端口
- IDS 网关入口端口
- 默认前端回源 IP / 端口
- 默认后端回源 IP / 端口
- 默认站点标识和名称
- 附加端口入口映射
- 域名入口映射

这些参数会写入：

- `config/ids-backend.env`
- `ids-data/state/communication_settings.json`

## 前端配置与 Docker 的关系

- 在 IDS 前端保存默认回源地址、域名映射、站点标识后，重启 `ids-gateway` 即可生效。
- 如果你修改了“入口端口”或新增了“附加端口入口”，还需要重新执行 `start-ids-docker.*`，让 Docker Compose 同步宿主机端口映射。

## 镜像仓库部署

统一入口脚本支持两种模式：

- `local`：从当前交付包直接本地构建镜像
- `registry`：从镜像仓库拉取运行镜像

阿里云 ACR 单仓库示例：

```bash
docker login --username=nick0442454023 crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com
./start-ids-docker.sh --deploy-mode registry --image-prefix crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu --image-tag v2 --single-repo
```

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-ids-docker.ps1 -DeployMode registry -ImagePrefix crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu -ImageTag v2 -SingleRepo
```
