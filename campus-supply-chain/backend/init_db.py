"""初始化数据库并插入预置业务数据"""
import sys
sys.path.insert(0, ".")

from app.database import SessionLocal, engine, Base
from app.schema_sync import ensure_schema
from app.models import User, Goods, Supplier
from app.core.security import get_password_hash
from app.demo_dataset_cohesive import apply_cohesive_demo

Base.metadata.create_all(bind=engine)
ensure_schema(engine)

db = SessionLocal()

# 预置用户（密码均为 123456）
DEMO_USERS = [
    {"username": "system_admin", "real_name": "管理员", "role": "system_admin"},
    {"username": "logistics_admin", "real_name": "后勤管理员", "role": "logistics_admin"},
    {"username": "warehouse_procurement", "real_name": "仓储采购员", "role": "warehouse_procurement"},
    {"username": "campus_supplier", "real_name": "校园合作供应商", "role": "campus_supplier"},
    {"username": "counselor_teacher", "real_name": "张老师", "role": "counselor_teacher"},
]

for u in DEMO_USERS:
    user = db.query(User).filter(User.username == u["username"]).first()
    if not user:
        user = User(
            username=u["username"],
            hashed_password=get_password_hash("123456"),
            real_name=u["real_name"],
            role=u["role"],
        )
        db.add(user)
    else:
        # 预置账号每次初始化都重置为统一口令，避免旧库口令漂移导致“无法登录”
        user.hashed_password = get_password_hash("123456")
        user.real_name = u["real_name"]
        user.role = u["role"]

# 兼容迁移：老角色 -> 新角色（避免旧数据库权限错乱）
old_to_new_role = {
    "admin": "system_admin",
    "procurement": "warehouse_procurement",
    "supplier": "campus_supplier",
    "teacher": "counselor_teacher",
}
for u in db.query(User).all():
    if u.role in old_to_new_role:
        u.role = old_to_new_role[u.role]

# 多名教师账号（采购申请人随机分配，密码均为 123456）
for un, rn in [
    ("teacher_li", "李老师"),
    ("teacher_wang", "王老师"),
    ("teacher_zhao", "赵老师"),
    ("teacher_liu", "刘老师"),
    ("teacher_chen", "陈老师"),
]:
    tu = db.query(User).filter(User.username == un).first()
    if not tu:
        db.add(
            User(
                username=un,
                hashed_password=get_password_hash("123456"),
                real_name=rn,
                role="counselor_teacher",
            )
        )
    else:
        tu.hashed_password = get_password_hash("123456")
        tu.real_name = rn
        tu.role = "counselor_teacher"

# 预置物资（含班会茶歇常用）
DEMO_GOODS = [
    {"name": "大米", "category": "食材", "spec": "25kg/袋", "unit": "袋", "safety_level": "high", "shelf_life_days": 180},
    {"name": "食用油", "category": "食材", "spec": "5L/桶", "unit": "桶", "safety_level": "high", "shelf_life_days": 365},
    {"name": "面粉", "category": "食材", "spec": "25kg/袋", "unit": "袋", "safety_level": "medium", "shelf_life_days": 180},
    {"name": "口罩", "category": "防疫", "spec": "50只/盒", "unit": "盒", "safety_level": "medium", "shelf_life_days": 365},
    {"name": "矿泉水", "category": "饮品", "spec": "550ml/瓶", "unit": "瓶", "safety_level": "medium", "shelf_life_days": 365},
    {"name": "小零食", "category": "茶歇", "spec": "独立包装", "unit": "份", "safety_level": "medium", "shelf_life_days": 90},
    {"name": "纸巾", "category": "茶歇", "spec": "抽纸", "unit": "盒", "safety_level": "low", "shelf_life_days": 365},
    {"name": "茶包", "category": "茶歇", "spec": "红茶/绿茶", "unit": "盒", "safety_level": "low", "shelf_life_days": 365},
    # 比赛场景（纸质/信息/答辩/实操）
    {"name": "A4打印纸", "category": "办公", "spec": "500张/包", "unit": "包", "safety_level": "medium", "shelf_life_days": 3650},
    {"name": "签字笔", "category": "办公", "spec": "黑色中性笔", "unit": "支", "safety_level": "medium", "shelf_life_days": 3650},
    {"name": "2B铅笔", "category": "办公", "spec": "考试专用", "unit": "支", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "橡皮", "category": "办公", "spec": "学生橡皮", "unit": "块", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "插线板", "category": "设备", "spec": "6位", "unit": "个", "safety_level": "high", "shelf_life_days": 3650},
    {"name": "网线", "category": "设备", "spec": "5米", "unit": "根", "safety_level": "medium", "shelf_life_days": 3650},
    {"name": "备用鼠标", "category": "设备", "spec": "USB有线", "unit": "个", "safety_level": "medium", "shelf_life_days": 3650},
    {"name": "备用键盘", "category": "设备", "spec": "USB有线", "unit": "个", "safety_level": "medium", "shelf_life_days": 3650},
    {"name": "激光笔", "category": "设备", "spec": "翻页激光笔", "unit": "支", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "5号电池", "category": "设备", "spec": "碱性电池", "unit": "节", "safety_level": "medium", "shelf_life_days": 1825},
    {"name": "计时器", "category": "设备", "spec": "电子计时器", "unit": "个", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "绝缘胶带", "category": "设备", "spec": "电工胶带", "unit": "卷", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "扎带", "category": "设备", "spec": "尼龙扎带", "unit": "包", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "螺丝刀套装", "category": "设备", "spec": "多功能", "unit": "套", "safety_level": "low", "shelf_life_days": 3650},
    {"name": "备用电池包", "category": "设备", "spec": "锂电池组", "unit": "包", "safety_level": "medium", "shelf_life_days": 1825},
    {"name": "玻片", "category": "实验", "spec": "载玻片 50片/盒", "unit": "盒", "safety_level": "medium", "shelf_life_days": 1095},
    {"name": "消毒酒精", "category": "防疫", "spec": "500ml/瓶", "unit": "瓶", "safety_level": "high", "shelf_life_days": 730},
    {"name": "薯片", "category": "茶歇", "spec": "桶装", "unit": "桶", "safety_level": "low", "shelf_life_days": 180},
]
for g in DEMO_GOODS:
    if not db.query(Goods).filter(Goods.name == g["name"]).first():
        db.add(Goods(**g))

# 预置供应商
for name in ["XX食品有限公司", "YY粮油公司"]:
    if not db.query(Supplier).filter(Supplier.name == name).first():
        db.add(Supplier(name=name, contact="负责人", phone="13800138000"))
db.flush()

# 供应商账号绑定公司，确保 supplier1 能看到“我的订单”
supplier_user = db.query(User).filter(User.username.in_(["campus_supplier", "supplier1"])).order_by(User.id.asc()).first()
supplier_company = db.query(Supplier).filter(Supplier.name == "XX食品有限公司").first()
if supplier_user and supplier_company and supplier_user.supplier_id != supplier_company.id:
    supplier_user.supplier_id = supplier_company.id

# 完整业务链路预置：POCHAIN-* 采购单、溯源、配送、出入库、多批次库存（首次执行写入，见 demo_dataset_cohesive）
if apply_cohesive_demo(db, force=False):
    print("[init_db] 已写入 POCHAIN 完整链路数据（订单/溯源/库存/审计）。重建请执行: python -m app.demo_dataset_cohesive --force")

db.commit()

print("初始化完成。预置账号：system_admin / logistics_admin / warehouse_procurement / campus_supplier / counselor_teacher，密码：123456")
db.close()
