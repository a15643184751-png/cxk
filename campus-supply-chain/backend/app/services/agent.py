"""智能体：真 agent（工具调用）优先，LLM 规则降级"""
import json
import re
from sqlalchemy.orm import Session
from ..models.goods import Goods
from ..models.stock import Inventory
from ..models.purchase import Purchase
from ..utils.llm_client import chat as llm_chat
from ..config import settings
from .agent_tools import (
    process_chat_agent,
    process_chat_admin,
    process_chat_warehouse,
    process_teacher_plain_dialog,
)

# 教师自由输入中含以下意图时，即使未点快捷场景也走工具智能体（申领/清单/库存等）
_TEACHER_AGENT_HINT = re.compile(
    r"(申领|采购清单|申购|申请单|生成清单|拟申购|一键|答题卡|草稿纸|密封条|茶歇|体检|留守|"
    r"桶装水|矿泉水|打印纸|订书钉|投影仪|溯源|配送单|订单|库存|短缺|预警|补货|复购|"
    r"后勤|仓储|WMS|额度|人数|\d+\s*人)",
    re.I,
)


def _teacher_message_suggests_agent(msg: str) -> bool:
    t = (msg or "").strip()
    if not t:
        return False
    return bool(_TEACHER_AGENT_HINT.search(t))

DEMO_TRIGGERS = ["短缺", "补货", "缺什么", "需要补", "什么缺少", "可能短缺", "采购", "订", "买", "要什么"]

ACTIVITY_TRIGGERS = [
    "讲座", "茶歇", "活动", "团建", "聚餐", "午餐", "会议", "培训",
    "200人", "100人", "50人", "人讲座", "人参加", "人活动",
    "准备", "需要", "要准备", "物资", "食材", "用品",
]

SCENE_HINTS = {
    "competition": ["比赛", "竞赛", "笔试", "机试", "编程赛", "答辩赛", "演讲赛"],
    "tea_break": ["茶歇", "班会", "讲座", "会议", "培训", "活动"],
    "lab": ["实验", "耗材", "实验室", "试剂", "器材"],
    "restock": ["补货", "短缺", "库存不足", "缺货"],
}

COMP_TYPE_KEYWORDS = {
    "纸质笔试": ["纸质", "笔试", "纸笔", "试卷"],
    "信息编程": ["信息", "编程", "机试", "上机", "算法"],
    "演讲答辩": ["演讲", "答辩", "路演", "汇报"],
    "机器人实操": ["机器人", "硬件", "电路", "实操"],
}

COMP_VENUE_KEYWORDS = {
    "普通教室": ["教室", "多媒体", "班会教室"],
    "机房": ["机房", "上机房"],
    "实验室": ["实验室", "实训室"],
    "报告厅": ["报告厅", "礼堂", "讲堂"],
}

COMP_SUPPORT_KEYWORDS = {
    "基础保障": ["基础保障", "基础", "简版"],
    "标准保障": ["标准保障", "标准", "正常"],
    "加强保障": ["加强保障", "加强", "高保障", "高规格"],
}


def _is_shortage_question(q: str) -> bool:
    return any(t in (q or "") for t in DEMO_TRIGGERS)


def _is_activity_request(q: str) -> bool:
    """活动/讲座等自然语言需求：需要茶歇、午餐、物资等"""
    return any(t in (q or "") for t in ACTIVITY_TRIGGERS)


def _extract_people_count(text: str) -> int | None:
    m = re.search(r"(\d{1,4})\s*人", text or "")
    if not m:
        return None
    try:
        n = int(m.group(1))
        return n if n > 0 else None
    except Exception:
        return None


def _extract_duration_hours(text: str) -> float | None:
    t = text or ""
    h = re.search(r"(\d+(?:\.\d+)?)\s*小时", t)
    if h:
        try:
            return float(h.group(1))
        except Exception:
            return None
    m = re.search(r"(\d{1,3})\s*分钟", t)
    if m:
        try:
            return max(0.5, int(m.group(1)) / 60.0)
        except Exception:
            return None
    if "半天" in t:
        return 4.0
    if "一天" in t:
        return 8.0
    return None


def _scene_name(message: str) -> str | None:
    text = message or ""
    for k, words in SCENE_HINTS.items():
        if any(w in text for w in words):
            return k
    return None


def _pick_by_keywords(text: str, options: dict[str, list[str]]) -> str | None:
    t = text or ""
    for label, keys in options.items():
        if label in t:
            return label
        if any(k in t for k in keys):
            return label
    return None


def _append_if_exists(goods_names: set[str], out_items: list[dict], name: str, quantity: float, unit: str):
    if name in goods_names and quantity > 0:
        out_items.append({"name": name, "quantity": round(float(quantity), 2), "unit": unit})


def _build_competition_items(db: Session, comp_type: str, support: str, people: int, duration_hours: float) -> list[dict]:
    """比赛保障模板：先抽象决策，再按人数/时长缩放。"""
    goods_names = {g.name for g in db.query(Goods).filter(Goods.is_active == True).all()}
    support_factor = {"基础保障": 1.0, "标准保障": 1.2, "加强保障": 1.5}.get(support, 1.2)
    duration_factor = 1.0 if duration_hours <= 2 else (1.2 if duration_hours <= 4 else 1.4)
    factor = support_factor * duration_factor

    items: list[dict] = []
    if comp_type == "纸质笔试":
        _append_if_exists(goods_names, items, "A4打印纸", max(1, people / 20) * factor, "包")
        _append_if_exists(goods_names, items, "签字笔", people * 1.1 * factor, "支")
        _append_if_exists(goods_names, items, "2B铅笔", people * factor, "支")
        _append_if_exists(goods_names, items, "橡皮", max(1, people / 2) * factor, "块")
        _append_if_exists(goods_names, items, "矿泉水", people * 0.8 * factor, "瓶")
    elif comp_type == "信息编程":
        _append_if_exists(goods_names, items, "插线板", max(1, people / 6) * factor, "个")
        _append_if_exists(goods_names, items, "网线", max(1, people / 8) * factor, "根")
        _append_if_exists(goods_names, items, "备用鼠标", max(1, people / 10) * factor, "个")
        _append_if_exists(goods_names, items, "备用键盘", max(1, people / 15) * factor, "个")
        _append_if_exists(goods_names, items, "矿泉水", people * 0.8 * factor, "瓶")
        _append_if_exists(goods_names, items, "纸巾", max(1, people / 30) * factor, "盒")
    elif comp_type == "演讲答辩":
        _append_if_exists(goods_names, items, "激光笔", max(1, people / 30) * factor, "支")
        _append_if_exists(goods_names, items, "5号电池", max(2, people / 12) * factor, "节")
        _append_if_exists(goods_names, items, "计时器", max(1, people / 40) * factor, "个")
        _append_if_exists(goods_names, items, "矿泉水", people * factor, "瓶")
        _append_if_exists(goods_names, items, "纸巾", max(1, people / 25) * factor, "盒")
    else:  # 机器人实操
        _append_if_exists(goods_names, items, "绝缘胶带", max(1, people / 20) * factor, "卷")
        _append_if_exists(goods_names, items, "扎带", max(1, people / 15) * factor, "包")
        _append_if_exists(goods_names, items, "螺丝刀套装", max(1, people / 25) * factor, "套")
        _append_if_exists(goods_names, items, "备用电池包", max(1, people / 18) * factor, "包")
        _append_if_exists(goods_names, items, "矿泉水", people * 0.8 * factor, "瓶")

    # 兜底：即便模板物资不全，也保证有可提交的默认清单
    if not items:
        _append_if_exists(goods_names, items, "矿泉水", max(10, people * 0.8), "瓶")
        _append_if_exists(goods_names, items, "纸巾", max(1, people / 25), "盒")
        _append_if_exists(goods_names, items, "小零食", max(10, people * 0.6), "份")
    return items


def _guided_competition_response(db: Session, full_text: str) -> dict:
    comp_type = _pick_by_keywords(full_text, COMP_TYPE_KEYWORDS)
    venue = _pick_by_keywords(full_text, COMP_VENUE_KEYWORDS)
    support = _pick_by_keywords(full_text, COMP_SUPPORT_KEYWORDS)
    people = _extract_people_count(full_text)
    duration_hours = _extract_duration_hours(full_text)

    if not comp_type:
        return {
            "reply": "我先帮你做比赛保障规划。请先选择比赛类型：",
            "react": [{"step": 1, "text": "识别场景：比赛保障"}, {"step": 2, "text": "优先补全抽象决策：比赛类型"}],
            "actions": [
                {"type": "quick_reply", "label": "纸质笔试", "payload": {"text": "纸质笔试"}},
                {"type": "quick_reply", "label": "信息编程", "payload": {"text": "信息编程比赛"}},
                {"type": "quick_reply", "label": "演讲答辩", "payload": {"text": "演讲答辩比赛"}},
                {"type": "quick_reply", "label": "机器人实操", "payload": {"text": "机器人实操比赛"}},
            ],
        }

    if not venue:
        return {
            "reply": f"已记录比赛类型：{comp_type}。请确认场地类型：",
            "react": [{"step": 1, "text": "已识别比赛类型"}, {"step": 2, "text": "补全抽象决策：场地条件"}],
            "actions": [
                {"type": "quick_reply", "label": "普通教室", "payload": {"text": "普通教室"}},
                {"type": "quick_reply", "label": "机房", "payload": {"text": "机房"}},
                {"type": "quick_reply", "label": "实验室", "payload": {"text": "实验室"}},
                {"type": "quick_reply", "label": "报告厅", "payload": {"text": "报告厅"}},
            ],
        }

    if not support:
        return {
            "reply": "请确认保障等级（会影响备件和冗余量）：",
            "react": [{"step": 1, "text": "已确定比赛类型和场地"}, {"step": 2, "text": "补全抽象决策：保障等级"}],
            "actions": [
                {"type": "quick_reply", "label": "基础保障", "payload": {"text": "基础保障"}},
                {"type": "quick_reply", "label": "标准保障", "payload": {"text": "标准保障"}},
                {"type": "quick_reply", "label": "加强保障", "payload": {"text": "加强保障"}},
            ],
        }

    if not people:
        return {
            "reply": "抽象策略已确定。请补充参赛规模：",
            "react": [{"step": 1, "text": "已完成抽象规划"}, {"step": 2, "text": "补全数量参数：人数"}],
            "actions": [
                {"type": "quick_reply", "label": "30人", "payload": {"text": "30人"}},
                {"type": "quick_reply", "label": "60人", "payload": {"text": "60人"}},
                {"type": "quick_reply", "label": "100人", "payload": {"text": "100人"}},
                {"type": "quick_reply", "label": "150人", "payload": {"text": "150人"}},
            ],
        }

    if not duration_hours:
        return {
            "reply": "请补充比赛时长（用于计算冗余量与饮水保障）：",
            "react": [{"step": 1, "text": "已确定人数"}, {"step": 2, "text": "补全数量参数：时长"}],
            "actions": [
                {"type": "quick_reply", "label": "2小时", "payload": {"text": "2小时"}},
                {"type": "quick_reply", "label": "半天", "payload": {"text": "半天"}},
                {"type": "quick_reply", "label": "一天", "payload": {"text": "一天"}},
            ],
        }

    items = _build_competition_items(db, comp_type, support, people, duration_hours)
    if not items:
        return {"reply": "当前物资目录缺少比赛场景物资，请先在物资管理新增后再生成清单。", "react": [], "actions": []}

    desc = [
        f"【场景】比赛保障（{comp_type}）",
        f"【抽象决策】场地：{venue}；保障等级：{support}",
        f"【规模参数】约 {people} 人，时长约 {duration_hours:g} 小时",
        "【拟申请清单】",
    ]
    for it in items:
        desc.append(f"• {it['name']} {it['quantity']}{it['unit']}")
    desc.append("如需调整可说“插线板增加到15个”或“改成基础保障”。确认后点击「确认提交」。")
    return {
        "reply": "\n".join(desc),
        "react": [
            {"step": 1, "text": "抽象规划：比赛类型/场地/保障等级"},
            {"step": 2, "text": "参数补全：人数与时长"},
            {"step": 3, "text": "按模板自动生成比赛保障清单"},
        ],
        "actions": [{"type": "create_purchase", "label": "确认提交", "payload": {"items": items}}],
    }


def _guided_tea_break_response(db: Session, full_text: str) -> dict:
    people = _extract_people_count(full_text)
    duration_hours = _extract_duration_hours(full_text)
    needs_water = ("矿泉水" in full_text) or ("饮用水" in full_text) or ("水" in full_text)
    needs_hot_water = ("热水" in full_text) or ("开水" in full_text) or ("茶" in full_text)

    if not people:
        return {
            "reply": "我先帮你收敛到「活动茶歇」场景。请确认参加人数（可直接点击）：",
            "react": [{"step": 1, "text": "识别场景：活动茶歇"}, {"step": 2, "text": "缺少人数，触发引导式补全"}],
            "actions": [
                {"type": "quick_reply", "label": "30人", "payload": {"text": "30人"}},
                {"type": "quick_reply", "label": "40人", "payload": {"text": "40人"}},
                {"type": "quick_reply", "label": "60人", "payload": {"text": "60人"}},
                {"type": "quick_reply", "label": "100人", "payload": {"text": "100人"}},
            ],
        }

    if not duration_hours:
        return {
            "reply": f"已记录人数约 {people} 人。请补充活动时长（可点击）：",
            "react": [{"step": 1, "text": "已提取人数"}, {"step": 2, "text": "缺少时长，继续补全"}],
            "actions": [
                {"type": "quick_reply", "label": "30分钟", "payload": {"text": "30分钟"}},
                {"type": "quick_reply", "label": "1小时", "payload": {"text": "1小时"}},
                {"type": "quick_reply", "label": "2小时", "payload": {"text": "2小时"}},
                {"type": "quick_reply", "label": "半天", "payload": {"text": "半天"}},
            ],
        }

    snack_qty = people
    water_qty = people if needs_water or not needs_hot_water else max(0, int(people * 0.4))
    tissue_qty = max(1, round(people / 25))
    tea_qty = max(1, round(people / 40)) if needs_hot_water else 0
    if duration_hours >= 2:
        snack_qty = int(people * 1.2)
        water_qty = max(water_qty, int(people * 1.2))

    items = []
    goods_names = {g.name for g in db.query(Goods).filter(Goods.is_active == True).all()}
    if "矿泉水" in goods_names:
        items.append({"name": "矿泉水", "quantity": water_qty, "unit": "瓶"})
    if "小零食" in goods_names:
        items.append({"name": "小零食", "quantity": snack_qty, "unit": "份"})
    if "纸巾" in goods_names:
        items.append({"name": "纸巾", "quantity": tissue_qty, "unit": "盒"})
    if tea_qty > 0 and "茶包" in goods_names:
        items.append({"name": "茶包", "quantity": tea_qty, "unit": "盒"})

    desc = [
        f"【场景】活动茶歇（约 {people} 人，时长约 {duration_hours:g} 小时）",
        "【拟申请清单】",
    ]
    for it in items:
        if it["name"] == "矿泉水":
            desc.append(f"• 矿泉水 {it['quantity']}瓶（{people}人 × 人均约 {it['quantity']/people:.1f} 瓶）")
        elif it["name"] == "小零食":
            desc.append(f"• 小零食 {it['quantity']}份（{people}人 × 人均约 {it['quantity']/people:.1f} 份）")
        else:
            desc.append(f"• {it['name']} {it['quantity']}{it['unit']}")
    desc.append("请确认上述清单；如需调整请直接说“矿泉水改成80瓶”或“去掉茶包”。确认无误可点「确认提交」。")
    return {
        "reply": "\n".join(desc),
        "react": [
            {"step": 1, "text": "场景化解析：活动茶歇"},
            {"step": 2, "text": "基于人数与时长计算建议数量"},
            {"step": 3, "text": "生成拟申请清单，等待确认后执行"},
        ],
        "actions": [{"type": "create_purchase", "label": "确认提交", "payload": {"items": items}}],
    }


def _guided_scene_response(db: Session, message: str, history: list | None = None) -> dict | None:
    """
    场景化引导：优先给可点击选项，减少手动输入。
    支持比赛规划（先抽象后数值）和茶歇场景。
    """
    full_text = " ".join([h.get("content", "") for h in (history or []) if h.get("role") == "user"] + [message or ""])
    scene = _scene_name(full_text)
    if not scene:
        return None
    if scene == "competition":
        return _guided_competition_response(db, full_text)
    if scene == "tea_break":
        return _guided_tea_break_response(db, full_text)
    return None


def _query_shortage_data(db: Session) -> list[dict]:
    """从数据库查询可能短缺的物资"""
    inventories = db.query(Inventory).all()
    goods_list = db.query(Goods).all()
    goods_by_name = {g.name: g for g in goods_list}

    results = []
    # 有库存记录的按 quantity 判断
    for inv in inventories:
        g = goods_by_name.get(inv.goods_name)
        safe_qty = 20 if g and getattr(g, "safety_level", "") == "high" else 10
        if inv.quantity < safe_qty:
            results.append({
                "name": inv.goods_name,
                "quantity": inv.quantity,
                "unit": inv.unit or "件",
                "level": "urgent" if inv.quantity < 5 else "warning",
                "suggest": max(0, safe_qty - inv.quantity),
            })
    # 若无库存数据，从物资表取前几条作为「需关注」
    if not results and goods_list:
        for g in goods_list[:5]:
            results.append({
                "name": f"{g.name} {g.spec}" if g.spec else g.name,
                "quantity": 0,
                "unit": g.unit or "件",
                "level": "warning",
                "suggest": 30,
            })
    return results


def build_shortage_response(db: Session) -> dict:
    """构建短缺分析响应（ReAct + 决策 + 动作）"""
    items = _query_shortage_data(db)
    urgent = [x for x in items if x["level"] == "urgent"]
    warning = [x for x in items if x["level"] == "warning"]

    lines = []
    if urgent:
        lines.append("【即将短缺】")
        for x in urgent:
            lines.append(f"• {x['name']}：当前约 {x['quantity']}{x['unit']}，建议 2 日内补货 {x['suggest']}{x['unit']}")
    if warning:
        lines.append("\n【建议提前预备】" if lines else "【建议提前预备】")
        for x in warning:
            lines.append(f"• {x['name']}：建议补货 {x['suggest']}{x['unit']}")

    if not lines:
        lines = ["当前库存充足，无紧急短缺。可关注常规补货节奏。"]

    reply = "\n".join(lines) + "\n\n点击下方「创建采购单」可一键生成补货申请。"

    actions_payload = {"items": []}
    for x in items[:5]:
        actions_payload["items"].append({
            "name": x["name"],
            "quantity": x.get("suggest", 30),
            "unit": x["unit"],
        })

    return {
        "reply": reply,
        "react": [
            {"step": 1, "text": "解析用户意图：查询短缺物资及补货建议"},
            {"step": 2, "text": "调用数据仓库：读取库存、安全库存、物资目录"},
            {"step": 3, "text": f"计算短缺风险：共 {len(items)} 项需关注"},
            {"step": 4, "text": "生成决策建议并编排可执行动作"},
        ],
        "actions": [
            {"type": "create_purchase", "label": "创建采购单", "payload": actions_payload},
        ] if actions_payload["items"] else [],
    }


def _try_llm_shortage(db: Session, message: str) -> dict | None:
    """尝试用 LLM 生成短缺分析响应，成功返回 dict，失败返回 None"""
    items = _query_shortage_data(db)
    inv_json = json.dumps(items, ensure_ascii=False)
    system = """你是校园采购短缺分析助手。根据库存数据分析可能短缺的物资并给出补货建议。
严格按以下 JSON 格式回复，不要其他文字：
{"reply":"自然语言分析结论，分【即将短缺】【建议提前预备】等段落","suggestions":[{"name":"物资名","quantity":数量,"unit":"单位"},...]}"""
    user = f"【库存数据】\n{inv_json}\n\n【用户问题】\n{message}"
    raw = llm_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    if not raw:
        return None
    raw = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(raw)
        suggestions = data.get("suggestions", [])
        actions = [{"type": "create_purchase", "label": "创建采购单", "payload": {"items": suggestions}}] if suggestions else []
        return {
            "reply": data.get("reply", ""),
            "react": [
                {"step": 1, "text": "解析用户意图：查询短缺物资及补货建议"},
                {"step": 2, "text": "调用数据仓库：读取库存、安全库存"},
                {"step": 3, "text": f"调用 LLM 分析：共 {len(suggestions)} 项补货建议"},
                {"step": 4, "text": "生成决策并编排可执行动作"},
            ],
            "actions": actions,
        }
    except Exception:
        return None


def _build_business_context(db: Session) -> str:
    """从本地数据库构建业务上下文，供 LLM 参考"""
    parts = []
    goods_list = db.query(Goods).filter(Goods.is_active == True).limit(30).all()
    # 完整列出物资名和单位，便于 LLM 严格匹配
    goods_lines = [f"- {g.name}（{g.unit or '件'}）" for g in goods_list]
    if goods_lines:
        parts.append("【物资目录】必须从以下名单选取，物资名需完全一致：\n" + "\n".join(goods_lines))

    invs = db.query(Inventory).filter(Inventory.quantity > 0).limit(20).all()
    if invs:
        inv_lines = [f"{i.goods_name}：{i.quantity}{i.unit or '件'}" for i in invs[:10]]
        parts.append(f"【当前库存】{'; '.join(inv_lines)}（可优先使用库存后再补充采购）")

    recent = db.query(Purchase).order_by(Purchase.created_at.desc()).limit(5).all()
    if recent:
        p_lines = [f"{p.order_no}({p.status})" for p in recent]
        parts.append(f"【近期采购】{'; '.join(p_lines)}")

    if not parts:
        return "【本地数据】暂无业务数据。"
    return "【本地数据】\n" + "\n".join(parts)


def _try_llm_activity(db: Session, message: str) -> dict | None:
    """活动类需求：解析人数、场景，给出物资建议并生成可执行动作"""
    context = _build_business_context(db)
    system = """你是校园物资采购助手。用户会描述活动需求（如班会茶歇、讲座、团建等）。
要求：
1. 从【物资目录】中选取物资，name 必须与目录完全一致
2. 数量按「人数×人均用量」计算，在 reply 中写明计算依据（如：40人×1瓶=40瓶）
3. reply 必须 explicitly 列出每项采购建议，格式：• 物资名 数量单位（计算依据）
4. suggestions 的 name/unit 与物资目录一致

严格按以下 JSON 格式回复，不要其他文字：
{"reply":"【活动建议】简要说明规模、时长。\n【采购清单】\n• 物资名 数量单位（如：40人×1=40瓶）\n• ...\n【说明】可补充库存使用建议等","suggestions":[{"name":"物资名","quantity":数量,"unit":"单位"},...]}"""
    user = f"{context}\n\n【用户需求】\n{message}"
    raw = llm_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    if not raw:
        return None
    raw = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(raw)
        suggestions = data.get("suggestions", [])
        actions = (
            [{"type": "create_purchase", "label": "提交采购申请", "payload": {"items": suggestions}}]
            if suggestions
            else []
        )
        reply = data.get("reply", "").strip()
        if not reply.endswith("提交申请"):
            reply += "\n\n确认无误后，点击下方「提交采购申请」生成申请单，等待管理员审批。"
        return {
            "reply": reply,
            "react": [
                {"step": 1, "text": "解析用户意图：活动/讲座等物资需求"},
                {"step": 2, "text": "调用 LLM 分析人数与场景"},
                {"step": 3, "text": f"匹配物资目录，生成 {len(suggestions)} 项采购建议"},
                {"step": 4, "text": "编排可执行动作：提交采购申请"},
            ],
            "actions": actions,
        }
    except Exception:
        return None


def _build_activity_fallback(message: str) -> dict:
    """活动类需求的规则降级：给出一组通用茶歇/会议物资建议（与物资目录一致）"""
    items = [
        {"name": "矿泉水", "quantity": 40, "unit": "瓶"},
        {"name": "小零食", "quantity": 40, "unit": "份"},
        {"name": "纸巾", "quantity": 2, "unit": "盒"},
        {"name": "茶包", "quantity": 1, "unit": "盒"},
    ]
    return {
        "reply": "【采购清单】根据活动规模建议：\n• 矿泉水 40瓶（人均1瓶）\n• 小零食 40份（人均1份）\n• 纸巾 2盒\n• 茶包 1盒\n\n确认后点击下方「提交采购申请」。",
        "react": [
            {"step": 1, "text": "解析用户意图：活动物资需求"},
            {"step": 2, "text": "规则引擎：生成通用茶歇物资建议"},
            {"step": 3, "text": "编排可执行动作"},
        ],
        "actions": [{"type": "create_purchase", "label": "提交采购申请", "payload": {"items": items}}],
    }


def _try_llm_general(db: Session, message: str) -> dict | None:
    """通用对话：LLM 基于本地数据生成自然语言回复"""
    context = _build_business_context(db)
    system = """你是校园物资供应链智能助手，负责帮助教职工、采购员处理采购、库存、配送等问题。
你将收到【本地数据】作为参考，请基于这些真实数据回答用户问题。
你可以：
- 根据物资目录、库存、采购记录回答咨询
- 协助生成采购建议（可结合库存数据）
- 解释供应链流程
回复要简洁、专业、友好，尽量引用具体数据。若数据不足，可说明并建议用户补充或使用「现在什么物资可能短缺」获取完整分析。"""
    user = f"{context}\n\n【用户问题】\n{message}"
    raw = llm_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    if not raw or not raw.strip():
        return None
    return {
        "reply": raw.strip(),
        "react": [
            {"step": 1, "text": "解析用户意图"},
            {"step": 2, "text": "调用 LLM 生成回复"},
        ],
        "actions": [],
    }


def process_chat(
    db: Session,
    message: str,
    applicant_id: int | None = None,
    history: list | None = None,
    user_role: str = "",
    caller_display_name: str | None = None,
    use_agent: bool = False,
) -> dict:
    """处理用户消息：按角色分流，真智能体优先，否则规则降级。"""
    role = (user_role or "").strip()

    # 管理员：审计、反腐、供应商分析
    if role == "system_admin":
        result = process_chat_admin(db, message, history)
        if result:
            return result

    # 仓管：仓储效率、出入库建议
    if role == "warehouse_procurement":
        result = process_chat_warehouse(db, message, history)
        if result:
            return result

    # 教师：默认纯对话（小链直接回复）；use_agent 或文案含申领/库存等意图时走工具智能体
    teacher_tried_agent = False
    if role == "counselor_teacher":
        if settings.LLM_BASE_URL and settings.LLM_PROVIDER in ("deepseek", "openai"):
            force_agent = bool(use_agent) or _teacher_message_suggests_agent(message)
            if not force_agent:
                plain = process_teacher_plain_dialog(db, message, history, caller_display_name)
                if plain and plain.get("reply"):
                    return plain
            agent_res = process_chat_agent(
                db, message, applicant_id, history, user_role=role, caller_display_name=caller_display_name
            )
            teacher_tried_agent = True
            if agent_res.get("reply"):
                return agent_res
        guided = _guided_scene_response(db, message, history)
        if guided:
            return guided

    # 其他角色：真智能体（工具调用）优先
    if settings.LLM_BASE_URL and settings.LLM_PROVIDER in ("deepseek", "openai"):
        if not teacher_tried_agent:
            result = process_chat_agent(
                db, message, applicant_id, history, user_role=role, caller_display_name=caller_display_name
            )
            if result.get("reply"):
                return result
            print("[Agent] 真智能体返回空，降级到规则引擎")

    # 1. 短缺类问题（采购/后勤）：LLM 结构化分析 或 规则引擎
    if _is_shortage_question(message):
        if settings.LLM_BASE_URL:
            result = _try_llm_shortage(db, message)
            if result:
                return result
            print("[Agent] 短缺分析 LLM 失败，使用规则引擎")
        return build_shortage_response(db)

    # 2. 活动类需求（讲座茶歇、团建等）：LLM 解析并返回可执行动作
    if _is_activity_request(message):
        if settings.LLM_BASE_URL:
            result = _try_llm_activity(db, message)
            if result:
                return result
            print("[Agent] 活动需求 LLM 失败，使用规则降级")
        return _build_activity_fallback(message)

    # 3. 非短缺、非活动问题：若有 LLM 则通用对话（注入本地数据上下文），否则给出友好指引
    if settings.LLM_BASE_URL:
        result = _try_llm_general(db, message)
        if result:
            return result
        print("[Agent] 通用对话 LLM 返回空，检查 DeepSeek API Key 和网络")
        # LLM 已配置但调用失败
        return {
            "reply": "大模型调用失败，请检查：\n• backend/.env 中 LLM_API_KEY 是否有效、是否有余额\n• 网络是否能访问 DeepSeek API\n• 后端终端是否有「LLM 调用失败」日志\n\n你可先试试：「现在什么物资可能短缺？」（此功能不依赖 LLM）",
            "react": [],
            "actions": [],
        }

    return {
        "reply": "你好！我是采购智能体。\n\n当前未配置大模型。请在 backend/.env 中配置：\n• LLM_PROVIDER=deepseek\n• LLM_BASE_URL=https://api.deepseek.com\n• LLM_API_KEY=你的Key\n\n配置后重启后端。或试试：「现在什么物资可能短缺？」（规则引擎即可回答）",
        "react": [],
        "actions": [],
    }
