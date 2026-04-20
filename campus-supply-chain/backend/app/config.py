from pathlib import Path
import os
import sys
from pydantic_settings import BaseSettings
from pydantic import field_validator

# 匹配常见内网 HTTP 来源（192.168/10/172.16-31），便于局域网手机/其他电脑访问前端 dev server
PRIVATE_LAN_CORS_REGEX = (
    r"^http://("
    r"192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
)

# 确保从 backend 目录加载 .env（无论启动路径）
_env_file = Path(__file__).resolve().parent.parent / ".env"

# 强制预先加载 .env（覆盖可能存在的空值，解决 uvicorn 子进程环境不同步）
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k:
                    os.environ[k] = v  # 直接覆盖，确保 .env 生效


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./supply_chain.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_sqlite_url_for_local_windows(cls, v):
        """Docker 使用 sqlite:////data/supply_chain.db；若在 Windows 本机 .env 误抄该值会无法打开库。"""
        if v is None:
            return v
        s = str(v).strip()
        if sys.platform == "win32" and s == "sqlite:////data/supply_chain.db":
            return "sqlite:///./supply_chain.db"
        return v

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # CORS（开发环境放宽，生产请收紧）
    # 通过 Nginx 同源部署时无需修改；同一局域网可加 http://本机IP:80 或 :5173
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",  # vite preview
        "http://localhost:8080", "http://127.0.0.1:8080",  # Docker Nginx
        "http://localhost:8166", "http://127.0.0.1:8166",  # 同源直连
        "http://localhost", "http://127.0.0.1",  # 小皮 80 端口
    ]

    # 为 true 时额外允许 PRIVATE_LAN_CORS_REGEX 匹配的来源（生产环境可设为 false）
    CORS_ALLOW_PRIVATE_NETWORKS: bool = True

    # IDS：请求体参与检测时的最大字节（过大不读满，避免内存压力）
    IDS_MAX_BODY_BYTES: int = 8192
    # IDS：命中后是否尝试 Windows 防火墙封禁（非 Windows 自动跳过）
    IDS_FIREWALL_BLOCK: bool = True
    # IDS：命中后是否异步调用 LLM 生成研判（需配置 LLM；失败则仅规则结果）
    IDS_AI_ANALYSIS: bool = True
    # IDS：达到此分值即阻断（其余仅记录）
    IDS_BLOCK_THRESHOLD: int = 70
    IDS_STANDALONE_ENABLED: bool = True
    IDS_STANDALONE_BASE_URL: str | None = "http://127.0.0.1:8170"
    IDS_STANDALONE_TIMEOUT_SECONDS: float = 8.0
    IDS_STANDALONE_INTEGRATION_TOKEN: str | None = None
    IDS_STANDALONE_SOURCE_SYSTEM: str = "campus_supply_chain_site"

    # LLM 智能体（可选，不配置则用规则引擎）
    LLM_PROVIDER: str = "ollama"  # ollama | openai | deepseek
    LLM_BASE_URL: str | None = None  # 如 http://127.0.0.1:11434 则启用 Ollama
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "qwen2:7b"  # Ollama 模型名，或 openai 的 model

    @field_validator("LLM_BASE_URL", "IDS_STANDALONE_BASE_URL", "IDS_STANDALONE_INTEGRATION_TOKEN", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    class Config:
        env_file = str(_env_file) if _env_file.exists() else None
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
