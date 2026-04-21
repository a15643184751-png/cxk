import json
from pathlib import Path
import os
import sys

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings


PRIVATE_LAN_CORS_REGEX = (
    r"^http://("
    r"192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
)

APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = APP_DIR / "runtime"
DEFAULT_ACCEPTED_DIR = DEFAULT_DATA_DIR / "uploads" / "accepted"
DEFAULT_QUARANTINE_DIR = DEFAULT_DATA_DIR / "quarantine"
DEFAULT_REPORT_DIR = DEFAULT_DATA_DIR / "reports"
DEFAULT_OPERATOR_STATE_DIR = DEFAULT_DATA_DIR / "state"

_env_file = APP_DIR / ".env"

if _env_file.exists():
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k:
                    os.environ[k] = v


class GatewaySiteMapping(BaseModel):
    site_key: str = ""
    display_name: str = ""
    hosts: list[str] = []
    frontend_base_url: str = ""
    backend_base_url: str = ""

    @field_validator("site_key", "display_name", mode="before")
    @classmethod
    def normalize_text(cls, v):
        return str(v or "").strip()

    @field_validator("hosts", mode="before")
    @classmethod
    def parse_hosts(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            raw_items = v.split(",")
        else:
            raw_items = list(v)
        return [str(item or "").strip().lower().rstrip(".") for item in raw_items if str(item or "").strip()]

    @field_validator("frontend_base_url", "backend_base_url", mode="before")
    @classmethod
    def normalize_site_urls(cls, v):
        value = str(v or "").strip()
        return value.rstrip("/") if value else value


class GatewayPortMapping(BaseModel):
    site_key: str = ""
    display_name: str = ""
    ingress_port: int = 0
    frontend_base_url: str = ""
    backend_base_url: str = ""

    @field_validator("site_key", "display_name", mode="before")
    @classmethod
    def normalize_text(cls, v):
        return str(v or "").strip()

    @field_validator("ingress_port", mode="before")
    @classmethod
    def normalize_port(cls, v):
        if v is None or str(v).strip() == "":
            return 0
        return int(v)

    @field_validator("frontend_base_url", "backend_base_url", mode="before")
    @classmethod
    def normalize_site_urls(cls, v):
        value = str(v or "").strip()
        return value.rstrip("/") if value else value


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./ids.db"
    SECRET_KEY: str = "change-this-ids-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    IDS_DEFAULT_ADMIN_USERNAME: str = "ids_admin"
    IDS_DEFAULT_ADMIN_PASSWORD: str = "123456"
    IDS_DEFAULT_ADMIN_REAL_NAME: str = "IDS管理员"

    CORS_ORIGINS: list[str] = [
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:4175",
        "http://127.0.0.1:4175",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8170",
        "http://127.0.0.1:8170",
    ]
    CORS_ALLOW_PRIVATE_NETWORKS: bool = True

    IDS_MAX_BODY_BYTES: int = 8192
    IDS_FIREWALL_BLOCK: bool = False
    IDS_AI_ANALYSIS: bool = True
    IDS_BLOCK_THRESHOLD: int = 70
    IDS_INTEGRATION_TOKEN: str | None = None
    IDS_GATEWAY_DEFAULT_PORT: int = 8188
    IDS_GATEWAY_FRONTEND_BASE_URL: str = "http://127.0.0.1:5173"
    IDS_GATEWAY_BACKEND_BASE_URL: str = "http://127.0.0.1:8166"
    IDS_GATEWAY_SITE_MAP: list[GatewaySiteMapping] = []
    IDS_GATEWAY_PORT_MAP: list[GatewayPortMapping] = []
    IDS_GATEWAY_TIMEOUT_SECONDS: float = 30.0
    IDS_GATEWAY_MAX_CAPTURE_BYTES: int = 24576

    LLM_PROVIDER: str = "deepseek"
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "deepseek-chat"

    IDS_ACCEPTED_UPLOAD_DIR: str = str(DEFAULT_ACCEPTED_DIR)
    IDS_QUARANTINE_DIR: str = str(DEFAULT_QUARANTINE_DIR)
    IDS_REPORT_DIR: str = str(DEFAULT_REPORT_DIR)
    IDS_OPERATOR_STATE_DIR: str = str(DEFAULT_OPERATOR_STATE_DIR)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_sqlite_url(cls, v):
        if v is None:
            return v

        s = str(v).strip()
        prefix = "sqlite:///"
        if not s.startswith(prefix):
            return v

        if sys.platform == "win32" and s == "sqlite:////data/ids.db":
            return f"sqlite:///{(APP_DIR / 'ids.db').resolve().as_posix()}"

        raw_path = s[len(prefix) :]
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return v

        return f"sqlite:///{(APP_DIR / candidate).resolve().as_posix()}"

    @field_validator("LLM_BASE_URL", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("IDS_GATEWAY_FRONTEND_BASE_URL", "IDS_GATEWAY_BACKEND_BASE_URL", mode="before")
    @classmethod
    def normalize_gateway_url(cls, v):
        value = str(v or "").strip()
        return value.rstrip("/") if value else value

    @field_validator("IDS_GATEWAY_SITE_MAP", mode="before")
    @classmethod
    def parse_gateway_site_map(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            value = v.strip()
            if not value:
                return []
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return [parsed]
            return parsed
        return v

    @field_validator("IDS_GATEWAY_PORT_MAP", mode="before")
    @classmethod
    def parse_gateway_port_map(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            value = v.strip()
            if not value:
                return []
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return [parsed]
            return parsed
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
