"""填充业务流程数据：采购、入库、出库、库存、配送、溯源、预警"""
import sys
sys.path.insert(0, ".")

from sqlalchemy import text
from app.database import SessionLocal, Base, engine
from app.models import User, Supplier, Goods, Purchase, PurchaseItem
from app.models.stock import StockIn, StockOut, Inventory
from app.models.delivery import Delivery
from app.models.trace import TraceRecord
from app.models.warning import Warning

Base.metadata.create_all(bind=engine)

# 为 users 表添加 supplier_id（供应商角色关联公司）
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN supplier_id INTEGER"))
        conn.commit()
except Exception:
    pass

db = SessionLocal()

teacher = db.query(User).filter(User.role == "teacher").first()
procurement = db.query(User).filter(User.role == "procurement").first()
suppliers = db.query(Supplier).limit(20).all()

# 关联 supplier1 用户与首家供应商公司
supplier_user = db.query(User).filter(User.username == "supplier1").first()
if supplier_user and suppliers:
    supplier_user.supplier_id = suppliers[0].id
    db.flush()

if not teacher:
    print("请先运行 init_db.py 初始化用户")
    sys.exit(1)

# 常用物资用于构建业务流程
GOODS_FOR_FLOW = [
    ("东北大米", "袋", 10), ("小麦面粉", "袋", 5), ("大豆油", "桶", 5),
    ("鲜鸡蛋", "盒", 10), ("纯牛奶", "盒", 20), ("大白菜", "棵", 30),
    ("医用外科口罩", "袋", 50), ("84消毒液", "桶", 10), ("A4复印纸", "包", 20),
    ("中性签字笔", "支", 100), ("玻璃试管", "支", 50), ("医用酒精", "瓶", 30),
]

# === 1. 采购单（覆盖各状态） ===
PURCHASES = [
    ("PO20260301001", "pending", [
        ("东北大米", 20, "袋"), ("大豆油", 10, "桶"), ("鲜鸡蛋", 5, "盒"),
    ]),
    ("PO20260302002", "approved", [
        ("医用外科口罩", 100, "袋"), ("84消毒液", 5, "桶"), ("医用酒精", 20, "瓶"),
    ]),
    ("PO20260303003", "completed", [
        ("A4复印纸", 50, "包"), ("中性签字笔", 200, "支"), ("订书机", 5, "台"),
    ]),
    ("PO20260304004", "rejected", [("小麦面粉", 30, "袋")]),
    ("PO20260305005", "pending", [
        ("纯牛奶", 30, "盒"), ("大白菜", 50, "棵"), ("胡萝卜", 20, "袋"),
    ]),
    ("PO20260306006", "approved", [("玻璃试管", 20, "支"), ("玻璃烧杯", 10, "个")]),
    ("PO20260307007", "completed", [("东北大米", 50, "袋"), ("大豆油", 20, "桶")]),
    ("PO20260308008", "pending", [("免洗洗手液", 30, "瓶"), ("消毒湿巾", 20, "包")]),
    ("PO20260309009", "approved", [("西红柿", 15, "盒"), ("黄瓜", 20, "捆")]),
    ("PO20260310010", "completed", [("生物显微镜", 2, "台"), ("电子天平", 1, "台")]),
]

for idx, (order_no, status, items) in enumerate(PURCHASES):
    if db.query(Purchase).filter(Purchase.order_no == order_no).first():
        continue
    p = Purchase(order_no=order_no, status=status, applicant_id=teacher.id)
    if suppliers and status in ("approved", "completed"):
        # 部分订单分配给 suppliers[0]，便于 supplier1 看到
        p.supplier_id = suppliers[idx % max(1, len(suppliers))].id
    db.add(p)
    db.flush()
    for name, qty, unit in items:
        db.add(PurchaseItem(purchase_id=p.id, goods_name=name, quantity=qty, unit=unit))

# === 2. 入库单 ===
STOCK_INS = [
    ("IN20260301001", "东北大米", 50, "袋", "BATCH20260301001"),
    ("IN20260301002", "大豆油", 20, "桶", "BATCH20260301002"),
    ("IN20260302001", "医用外科口罩", 200, "袋", "BATCH20260302001"),
    ("IN20260302002", "84消毒液", 15, "桶", "BATCH20260302002"),
    ("IN20260303001", "A4复印纸", 100, "包", "BATCH20260303001"),
    ("IN20260304001", "鲜鸡蛋", 30, "盒", "BATCH20260304001"),
    ("IN20260305001", "纯牛奶", 40, "盒", "BATCH20260305001"),
    ("IN20260306001", "玻璃试管", 30, "支", "BATCH20260306001"),
    ("IN20260307001", "小麦面粉", 40, "袋", "BATCH20260307001"),
    ("IN20260308001", "医用酒精", 50, "瓶", "BATCH20260308001"),
    ("IN20260309001", "大白菜", 80, "棵", "BATCH20260309001"),
    ("IN20260310001", "中性签字笔", 300, "支", "BATCH20260310001"),
]

for order_no, gname, qty, unit, batch in STOCK_INS:
    if db.query(StockIn).filter(StockIn.order_no == order_no).first():
        continue
    db.add(StockIn(order_no=order_no, goods_name=gname, quantity=qty, unit=unit, batch_no=batch))

# === 3. 出库单 ===
STOCK_OUTS = [
    ("OUT20260301001", "东北大米", 15, "袋", "BATCH20260301001"),
    ("OUT20260301002", "大豆油", 5, "桶", "BATCH20260301002"),
    ("OUT20260302001", "医用外科口罩", 30, "袋", "BATCH20260302001"),
    ("OUT20260303001", "A4复印纸", 20, "包", "BATCH20260303001"),
    ("OUT20260304001", "鲜鸡蛋", 10, "盒", "BATCH20260304001"),
    ("OUT20260305001", "纯牛奶", 15, "盒", "BATCH20260305001"),
    ("OUT20260306001", "玻璃试管", 10, "支", "BATCH20260306001"),
    ("OUT20260307001", "84消毒液", 3, "桶", "BATCH20260302002"),
    ("OUT20260308001", "医用酒精", 12, "瓶", "BATCH20260308001"),
    ("OUT20260309001", "大白菜", 25, "棵", "BATCH20260309001"),
]

for order_no, gname, qty, unit, batch in STOCK_OUTS:
    if db.query(StockOut).filter(StockOut.order_no == order_no).first():
        continue
    db.add(StockOut(order_no=order_no, goods_name=gname, quantity=qty, unit=unit, batch_no=batch))

# === 4. 库存（部分低库存供 AI 短缺分析）===
INVENTORY_DATA = [
    ("东北大米", "食材", 8, "袋"),   # 低库存，触发短缺预警
    ("小麦面粉", "食材", 40, "袋"),
    ("大豆油", "食材", 15, "桶"),
    ("鲜鸡蛋", "食材", 20, "盒"),
    ("纯牛奶", "食材", 25, "盒"),
    ("大白菜", "食材", 55, "棵"),
    ("医用外科口罩", "防疫", 6, "袋"),  # 低库存
    ("84消毒液", "防疫", 12, "桶"),
    ("医用酒精", "防疫", 38, "瓶"),
    ("A4复印纸", "办公", 80, "包"),
    ("中性签字笔", "办公", 300, "支"),
    ("玻璃试管", "实验", 20, "支"),
]

db.query(Inventory).delete()
for gname, cat, qty, unit in INVENTORY_DATA:
    db.add(Inventory(goods_name=gname, category=cat, quantity=qty, unit=unit))

# === 5. 溯源记录（多批次） ===
TRACE_BATCHES = [
    ("BATCH20260301001", [
        ("供应商", "丰谷粮油有限公司"),
        ("采购", "采购单 PO20260307007"),
        ("入库", "入库单 IN20260301001"),
        ("仓储", "仓位 A-01"),
        ("配送", "食堂A 已签收"),
    ]),
    ("BATCH20260302001", [
        ("供应商", "安盾防护用品有限公司"),
        ("采购", "采购单 PO20260302002"),
        ("入库", "入库单 IN20260302001"),
        ("仓储", "仓位 B-02"),
    ]),
    ("BATCH20260304001", [
        ("供应商", "绿源食品有限公司"),
        ("采购", "采购单 PO20260301001"),
        ("入库", "入库单 IN20260304001"),
        ("仓储", "仓位 C-03"),
        ("配送", "食堂B 待配送"),
    ]),
    ("BATCH2024001", [
        ("供应商", "XX食品有限公司"),
        ("采购", "采购单 PO20240301001"),
        ("入库", "入库单 IN20240308001"),
        ("仓储", "仓位 A-01"),
        ("配送", "食堂A 已签收"),
    ]),
]

for batch_no, stages in TRACE_BATCHES:
    existing = db.query(TraceRecord).filter(TraceRecord.batch_no == batch_no).first()
    if existing:
        continue
    for stage, content in stages:
        db.add(TraceRecord(batch_no=batch_no, stage=stage, content=content))

# === 6. 配送单 ===
DELIVERIES = [
    ("DLV20260301001", "食堂A", "received"),
    ("DLV20260302002", "食堂B", "on_way"),
    ("DLV20260303003", "教学楼C", "loading"),
    ("DLV20260304004", "食堂A", "pending"),
    ("DLV20260305005", "实验楼D", "received"),
    ("DLV20260306006", "宿舍区E", "pending"),
    ("DLV20260307007", "食堂B", "received"),
    ("DLV20260308008", "行政楼F", "on_way"),
    ("DLV001", "食堂A", "received"),
]

for dno, dest, status in DELIVERIES:
    if db.query(Delivery).filter(Delivery.delivery_no == dno).first():
        continue
    db.add(Delivery(delivery_no=dno, destination=dest, status=status))

# === 7. 预警 ===
WARNINGS = [
    ("high", "东北大米", "库存低于安全线，3天内可能断货", "pending"),
    ("medium", "大豆油 5L", "临期7天，建议优先使用", "pending"),
    ("low", "大白菜", "库存充足，可关注补货节奏", "handled"),
    ("high", "医用外科口罩", "防疫物资低于安全库存", "pending"),
    ("medium", "鲜鸡蛋", "保质期短，建议本周内使用", "pending"),
    ("high", "84消毒液", "库存紧张，建议尽快补货", "handled"),
]

for level, material, desc, status in WARNINGS:
    if db.query(Warning).filter(Warning.material == material, Warning.description == desc).first():
        continue
    db.add(Warning(level=level, material=material, description=desc, status=status))

db.commit()
print("业务流程数据填充完成：")
print("  - 采购单:", db.query(Purchase).count())
print("  - 入库单:", db.query(StockIn).count())
print("  - 出库单:", db.query(StockOut).count())
print("  - 库存记录:", db.query(Inventory).count())
print("  - 溯源记录:", db.query(TraceRecord).count())
print("  - 配送单:", db.query(Delivery).count())
print("  - 预警:", db.query(Warning).count())
print("\n溯源可查批次号: BATCH20260301001, BATCH20260302001, BATCH20260304001, BATCH2024001")
db.close()
