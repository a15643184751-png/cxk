from __future__ import annotations

import json
from pathlib import Path


DEFAULT_ENV_PATH = Path(r"D:\ids\ids-standalone\ids-backend\.env")


def normalize_input(value: str) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def prompt_value(label: str, default: str = "", allow_empty: bool = False) -> str:
    while True:
        prompt = label
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        value = normalize_input(input(prompt))
        if value:
            return value
        if allow_empty:
            return ""
        if default:
            return default


def prompt_count(label: str, default: int = 0) -> int:
    while True:
        raw = normalize_input(input(f"{label} [{default}]: "))
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            value = -1
        if value >= 0:
            return value
        print("请输入 0 或正整数。")


def prompt_port(label: str, default: int) -> int:
    while True:
        raw = normalize_input(input(f"{label} [{default}]: "))
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            value = -1
        if 1 <= value <= 65535:
            return value
        print("请输入 1 到 65535 之间的端口。")


def read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def write_env_file(path: Path, data: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in data.items()]
    payload = "\n".join(lines) + "\n"
    with path.open("w", encoding="utf-8", errors="replace", newline="\n") as f:
        f.write(payload)


def main() -> int:
    env_path_raw = normalize_input(input(f"配置文件路径 [{DEFAULT_ENV_PATH}]: "))
    env_path = Path(env_path_raw) if env_path_raw else DEFAULT_ENV_PATH

    if not env_path.parent.exists():
        print(f"配置目录不存在: {env_path.parent}")
        return 1

    env_map = read_env_file(env_path)

    print("")
    print("当前模式：IDS 在一台机器，网站在另一台机器。")
    print("客户端统一访问 IDS 机器 IP + 入口端口，不直接访问网站机器。")
    print("")

    current_machine_ip = prompt_value("IDS 机器当前 IP（用于输出访问地址，可留空）", allow_empty=True)
    default_site_name = prompt_value("默认站点标识", "campus_supply_chain")
    default_gateway_port = prompt_port("默认站点入口端口", int(env_map.get("IDS_GATEWAY_DEFAULT_PORT", "8188") or 8188))
    default_frontend = prompt_value(
        "默认站点前端上游地址（例如 http://10.134.32.132:5173）",
        env_map.get("IDS_GATEWAY_FRONTEND_BASE_URL", "http://127.0.0.1:5173"),
    ).rstrip("/")
    default_backend = prompt_value(
        "默认站点后端上游地址（例如 http://10.134.32.132:8166）",
        env_map.get("IDS_GATEWAY_BACKEND_BASE_URL", "http://127.0.0.1:8166"),
    ).rstrip("/")
    extra_gateway_count = prompt_count("除默认站点外，还要接入几个网站", 0)

    port_map: list[dict[str, object]] = []
    used_ports = {default_gateway_port}
    for index in range(1, extra_gateway_count + 1):
        print(f"\n--- 额外入口 {index} ---")
        site_key = prompt_value("站点标识（site_key）", f"site{index}")
        display_name = prompt_value("站点显示名", site_key)

        suggested_port = 8288 + (index - 1) * 100
        while True:
            ingress_port = prompt_port("入口端口", suggested_port)
            if ingress_port not in used_ports:
                used_ports.add(ingress_port)
                break
            print(f"端口 {ingress_port} 已被占用，请换一个。")

        frontend_url = prompt_value(
            "该站点前端上游地址",
            "http://127.0.0.1:5173",
        ).rstrip("/")
        backend_url = prompt_value(
            "该站点后端上游地址",
            "http://127.0.0.1:8166",
        ).rstrip("/")

        port_map.append(
            {
                "site_key": site_key.strip(),
                "display_name": display_name.strip(),
                "ingress_port": ingress_port,
                "frontend_base_url": frontend_url,
                "backend_base_url": backend_url,
            }
        )

    env_map["IDS_GATEWAY_DEFAULT_PORT"] = str(default_gateway_port)
    env_map["IDS_GATEWAY_FRONTEND_BASE_URL"] = default_frontend
    env_map["IDS_GATEWAY_BACKEND_BASE_URL"] = default_backend
    env_map["IDS_GATEWAY_PORT_MAP"] = json.dumps(port_map, ensure_ascii=False, separators=(",", ":"))
    env_map["IDS_GATEWAY_SITE_MAP"] = "[]"

    write_env_file(env_path, env_map)

    print("\n多端口网关配置已写入。")
    print(f"配置文件: {env_path}")
    print(f"默认站点: {default_site_name}")
    print(f"  入口端口: {default_gateway_port}")
    print(f"  前端上游: {default_frontend}")
    print(f"  后端上游: {default_backend}")
    print(f"额外入口数: {len(port_map)}")
    for item in port_map:
        print(f"  - {item['display_name']} ({item['site_key']})")
        print(f"    ingress  -> :{item['ingress_port']}")
        print(f"    frontend -> {item['frontend_base_url']}")
        print(f"    backend  -> {item['backend_base_url']}")

    print("\n下一步：")
    print("1. 在网站机器上启动各业务站点，并确保端口与上面配置一致。")
    print("2. 在 IDS 机器上启动 IDS 前端、IDS 后端和网关。")
    print("3. 客户端统一访问 IDS 机器 IP + 入口端口，不再直接访问网站机器。")
    if current_machine_ip:
        print(f"   例如默认站点访问: http://{current_machine_ip}:{default_gateway_port}")
        for item in port_map:
            print(f"   {item['display_name']} 访问: http://{current_machine_ip}:{item['ingress_port']}")
        print(f"   IDS 控制台访问: http://{current_machine_ip}:5175")
    print("4. 如果要避免绕过 IDS，需要把网站机器业务端口的来源限制为 IDS 机器 IP。")
    print("5. 如果多个网站在同一台网站机器上，只需要为每个网站填写真实上游地址和端口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
