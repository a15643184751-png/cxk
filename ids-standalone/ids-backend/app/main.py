from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .api import auth, ids, traffic, upload
from .bootstrap import ensure_default_ids_admin, ensure_runtime_dirs
from .config import PRIVATE_LAN_CORS_REGEX, settings
from .database import Base, engine
from .middleware.ids_middleware import IDSMiddleware
from .schema_sync import ensure_schema
from .services.ids_runtime_bootstrap import bootstrap_ids_runtime_source
from .services.llm_startup import ensure_llm_ready_for_ids, llm_runtime_status

Base.metadata.create_all(bind=engine)
ensure_schema(engine)
ensure_runtime_dirs()

app = FastAPI(title="IDS API", version="1.0.0")

cors_options: dict = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.CORS_ALLOW_PRIVATE_NETWORKS:
    cors_options["allow_origin_regex"] = PRIVATE_LAN_CORS_REGEX

app.add_middleware(CORSMiddleware, **cors_options)
app.add_middleware(IDSMiddleware)


@app.on_event("startup")
def startup() -> None:
    ensure_runtime_dirs()
    admin = ensure_default_ids_admin()

    if settings.IDS_AI_ANALYSIS:
        ensure_llm_ready_for_ids()

    runtime_status = bootstrap_ids_runtime_source()
    print(
        "[startup] IDS runtime bootstrap: "
        f"status={runtime_status.get('status')}, "
        f"source={runtime_status.get('source_key')}, "
        f"package={runtime_status.get('package_version') or '-'}, "
        f"rules={runtime_status.get('rule_count')}"
    )

    llm_status = llm_runtime_status()
    print(
        "[startup] Upload audit mode: "
        f"{llm_status['upload_audit_label']} "
        f"(llm_configured={'yes' if llm_status['ready'] else 'no'}, "
        f"provider={llm_status['provider']}, model={llm_status['model']}, "
        f"base={llm_status['effective_base_url'] or '-'})"
    )
    print(
        "[startup] default IDS admin ready: "
        f"username={admin.username}, password={settings.IDS_DEFAULT_ADMIN_PASSWORD}"
    )


health_router = APIRouter(tags=["system"])


@health_router.get("/health")
def api_health() -> dict:
    llm_status = llm_runtime_status()
    return {
        "status": "ok",
        "service": "ids_api",
        "default_admin_username": settings.IDS_DEFAULT_ADMIN_USERNAME,
        "ids_ai_analysis_enabled": bool(settings.IDS_AI_ANALYSIS),
        "llm_configured": bool(llm_status["ready"]),
        "llm_provider": llm_status["provider"],
        "llm_model": llm_status["model"],
        "llm_required_field": llm_status["required_field"],
        "llm_base_url": llm_status["effective_base_url"] or None,
        "ids_upload_audit_mode": llm_status["upload_audit_mode"],
        "ids_upload_audit_label": llm_status["upload_audit_label"],
        "ids_upload_audit_message": llm_status["upload_audit_message"],
        "ids_upload_audit_mode_reason": llm_status["upload_audit_mode_reason"],
        "ids_upload_ai_active": bool(llm_status["upload_audit_mode"] == "llm_assisted"),
    }


app.include_router(health_router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(ids.router, prefix="/api")
app.include_router(traffic.router, prefix="/api")
app.include_router(upload.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"message": "IDS API", "docs": "/docs", "health": "/api/health"}


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)
