# Linux Pull Deployment

## 1. Configure Docker daemon

If you are pulling from the LAN registry on `10.134.32.132:5000`, add it to Docker's insecure registries:

```bash
sudo mkdir -p /etc/docker
cat <<'EOF' | sudo tee /etc/docker/daemon.json
{
  "insecure-registries": ["10.134.32.132:5000"]
}
EOF
sudo systemctl restart docker
```

Check:

```bash
docker info | grep -A5 "Insecure Registries"
curl http://10.134.32.132:5000/v2/_catalog
```

## 2. Pull images

```bash
docker pull 10.134.32.132:5000/campus-ids-runtime:v1
docker pull 10.134.32.132:5000/campus-ids-frontend:v1
```

`latest` is also available:

```bash
docker pull 10.134.32.132:5000/campus-ids-runtime:latest
docker pull 10.134.32.132:5000/campus-ids-frontend:latest
```

## 2A. Pull from Aliyun ACR single-repo mode

Login first:

```bash
docker login --username=nick0442454023 crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com
```

Then pull:

```bash
docker pull crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu:package-v2
docker pull crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu:runtime-v2
docker pull crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu:frontend-v2
```

Extract the delivery package to local disk:

```bash
mkdir -p ids-delivery
docker run --rm -v "$(pwd)/ids-delivery:/output" crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu:package-v2
cd ./ids-delivery/ids-docker-package
```

## 3. Deploy from the package directory

After extracting `ids-docker-package` on Linux:

```bash
cd ids-docker-package
chmod +x ./deploy-ids-registry.sh ./stop-ids-docker.sh
./deploy-ids-registry.sh 10.134.32.132:5000/campus-ids v1
```

For Aliyun ACR single-repo mode:

```bash
cd ids-docker-package
chmod +x ./start-ids-docker.sh ./configure-ids-core.sh ./deploy-ids-registry.sh ./stop-ids-docker.sh
./configure-ids-core.sh --deploy-mode registry --image-prefix crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu --image-tag v2 --single-repo
```

If you only want to generate runtime config and compose files first:

```bash
./deploy-ids-registry.sh 10.134.32.132:5000/campus-ids v1 --skip-start
```

For Aliyun ACR single-repo mode:

```bash
./configure-ids-core.sh --deploy-mode registry --image-prefix crpi-toxcpw80qqpdgjlh.cn-hangzhou.personal.cr.aliyuncs.com/wuhuhu/wuhuhu --image-tag v2 --single-repo --skip-start
```

## 4. Stop the services

```bash
./stop-ids-docker.sh
```

## 5. Images currently available in the registry

- `10.134.32.132:5000/campus-ids-runtime:v1`
- `10.134.32.132:5000/campus-ids-runtime:latest`
- `10.134.32.132:5000/campus-ids-frontend:v1`
- `10.134.32.132:5000/campus-ids-frontend:latest`

## 6. Important note

`start-ids-docker.*` is now a presentation bootstrap script.

It will:

- print decorative English status lines
- generate a bootstrap snapshot
- hand off into `configure-ids-core.*`

The actual deployment is still completed by:

- `configure-ids-core.*`
- `deploy-ids-runtime.*`
- `deploy-ids-registry.*`
