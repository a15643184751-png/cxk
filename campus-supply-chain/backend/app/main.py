from pathlib import Path
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import settings, PRIVATE_LAN_CORS_REGEX
from .database import engine, Base
from .api import auth, goods, ai, purchase, supplier, trace, warning, stock, delivery, dashboard, overview, audit, ids, upload
from .middleware.ids_middleware import IDSMiddleware
from .schema_sync import ensure_schema

# 创建表
Base.metadata.create_all(bind=engine)
ensure_schema(engine)

app = FastAPI(title="校园物资供应链安全监测平台 API", version="1.0.0")

_cors_kw: dict = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.CORS_ALLOW_PRIVATE_NETWORKS:
    _cors_kw["allow_origin_regex"] = PRIVATE_LAN_CORS_REGEX
app.add_middleware(CORSMiddleware, **_cors_kw)
app.add_middleware(IDSMiddleware)


@app.on_event("startup")
def startup():
    """启动时打印 LLM 配置状态，并确保 system_admin 存在"""
    u = getattr(settings, "LLM_BASE_URL", None)
    p = getattr(settings, "LLM_PROVIDER", "")
    print(f"[启动] LLM: {'已配置' if u else '未配置'} (provider={p}, base={u or '-'})")
    # 确保 system_admin 存在，避免登录 400
    from .database import SessionLocal
    from .models.user import User
    from .core.security import get_password_hash
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "system_admin").first()
        if not admin:
            legacy = db.query(User).filter(User.username == "admin").first()
            if legacy:
                legacy.role = "system_admin"
                legacy.real_name = legacy.real_name or "管理员"
            else:
                db.add(User(
                    username="system_admin",
                    hashed_password=get_password_hash("123456"),
                    real_name="管理员",
                    role="system_admin",
                ))
            db.commit()
            print("[启动] 已创建/更新 system_admin 账号（密码 123456）")
    finally:
        db.close()

# 健康检查等系统路由（优先注册，避免被其他路由覆盖）
_health_router = APIRouter(tags=["system"])
@_health_router.get("/health")
def api_health():
    return {"status": "ok", "llm_configured": bool(settings.LLM_BASE_URL), "llm_provider": settings.LLM_PROVIDER}
app.include_router(_health_router, prefix="/api")

# 所有路由挂在 /api 下，与前端 baseURL 一致
app.include_router(auth.router, prefix="/api")
app.include_router(goods.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(purchase.router, prefix="/api")
app.include_router(supplier.router, prefix="/api")
app.include_router(trace.router, prefix="/api")
app.include_router(warning.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(delivery.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(ids.router, prefix="/api")
app.include_router(upload.router, prefix="/api")

# 静态文件：上传文件访问
_uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

_materials_root = Path(__file__).resolve().parent.parent
_material_files = {
    "答题卡.jpg",
    "草稿纸.jpg",
    "中性笔.jpg",
    "密封条.jpg",
    "急救箱.jpg",
    "水.jpg",
}
_voice_files = {
    "采购信息提交语音.mp3",
    "采购信息判定异常语音.mp3",
    "采购待审批语音.mp3",
    "驳回申请语音.mp3",
    "出库成功语音.mp3",
}


@app.get("/materials/{filename}")
def material_image(filename: str):
    if filename not in _material_files:
        raise HTTPException(status_code=404, detail="material not found")
    p = _materials_root / filename
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="material missing")
    return FileResponse(str(p))


@app.get("/api/materials/{filename}")
def material_image_api(filename: str):
    return material_image(filename)


@app.get("/voice/{filename}")
def voice_audio(filename: str):
    if filename not in _voice_files:
        raise HTTPException(status_code=404, detail="voice not found")
    p = _materials_root / filename
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="voice missing")
    return FileResponse(str(p), media_type="audio/mpeg")


@app.get("/api/voice/{filename}")
def voice_audio_api(filename: str):
    return voice_audio(filename)


@app.get("/")
def root():
    return {"message": "Campus Supply Chain API", "docs": "/docs"}


@app.get("/favicon.ico")
def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

