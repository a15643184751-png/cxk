"""导入扩展供应商和物资数据"""
import sys
sys.path.insert(0, ".")

from sqlalchemy import text
from app.database import SessionLocal, Base, engine
from app.models import Supplier, Goods

Base.metadata.create_all(bind=engine)

# 为已有表添加新列（若表结构较旧）
def _migrate_columns():
    migrates = [
        ("suppliers", "code", "TEXT DEFAULT ''"),
        ("suppliers", "license_no", "TEXT DEFAULT ''"),
        ("suppliers", "license_url", "TEXT DEFAULT ''"),
        ("suppliers", "credit_score", "REAL DEFAULT 0"),
        ("suppliers", "quality_report_url", "TEXT DEFAULT ''"),
        ("suppliers", "is_blacklisted", "INTEGER DEFAULT 0"),
        ("goods", "health_standard", "TEXT DEFAULT ''"),
        ("goods", "description", "TEXT DEFAULT ''"),
        ("goods", "is_active", "INTEGER DEFAULT 1"),
    ]
    with engine.connect() as conn:
        for table, col, typ in migrates:
            try:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {typ}'))
                conn.commit()
            except Exception:
                conn.rollback()

_migrate_columns()
db = SessionLocal()

# 50 家供应商
SUPPLIERS = [
    {"name": "绿源食品有限公司", "code": "SUP001", "contact": "张经理", "phone": "13800138001", "address": "吉林省长春市南关区农业路123号", "license_no": "91220100MA12345678", "license_url": "https://example.com/license/sup001", "credit_score": 85.5, "quality_report_url": "https://example.com/report/sup001", "is_blacklisted": False},
    {"name": "康泰医疗器械有限公司", "code": "SUP002", "contact": "李经理", "phone": "13800138002", "address": "吉林省长春市朝阳区健康路456号", "license_no": "91220100MA23456789", "license_url": "https://example.com/license/sup002", "credit_score": 90.0, "quality_report_url": "https://example.com/report/sup002", "is_blacklisted": False},
    {"name": "晨光办公用品有限公司", "code": "SUP003", "contact": "王经理", "phone": "13800138003", "address": "吉林省长春市绿园区办公路789号", "license_no": "91220100MA34567890", "license_url": "https://example.com/license/sup003", "credit_score": 88.5, "quality_report_url": "https://example.com/report/sup003", "is_blacklisted": False},
    {"name": "科瑞实验设备有限公司", "code": "SUP004", "contact": "赵经理", "phone": "13800138004", "address": "吉林省长春市二道区科学路101号", "license_no": "91220100MA45678901", "license_url": "https://example.com/license/sup004", "credit_score": 92.0, "quality_report_url": "https://example.com/report/sup004", "is_blacklisted": False},
    {"name": "丰谷粮油有限公司", "code": "SUP005", "contact": "刘经理", "phone": "13800138005", "address": "吉林省长春市宽城区粮油路202号", "license_no": "91220100MA56789012", "license_url": "https://example.com/license/sup005", "credit_score": 82.0, "quality_report_url": "https://example.com/report/sup005", "is_blacklisted": False},
    {"name": "洁康消毒用品有限公司", "code": "SUP006", "contact": "孙经理", "phone": "13800138006", "address": "吉林省长春市南关区消毒路303号", "license_no": "91220100MA67890123", "license_url": "https://example.com/license/sup006", "credit_score": 87.5, "quality_report_url": "https://example.com/report/sup006", "is_blacklisted": False},
    {"name": "得力文具制造有限公司", "code": "SUP007", "contact": "周经理", "phone": "13800138007", "address": "吉林省长春市朝阳区文具路404号", "license_no": "91220100MA78901234", "license_url": "https://example.com/license/sup007", "credit_score": 91.0, "quality_report_url": "https://example.com/report/sup007", "is_blacklisted": False},
    {"name": "华仪实验仪器有限公司", "code": "SUP008", "contact": "吴经理", "phone": "13800138008", "address": "吉林省长春市绿园区仪器路505号", "license_no": "91220100MA89012345", "license_url": "https://example.com/license/sup008", "credit_score": 89.5, "quality_report_url": "https://example.com/report/sup008", "is_blacklisted": False},
    {"name": "新鲜达蔬菜配送有限公司", "code": "SUP009", "contact": "郑经理", "phone": "13800138009", "address": "吉林省长春市二道区蔬菜路606号", "license_no": "91220100MA90123456", "license_url": "https://example.com/license/sup009", "credit_score": 84.0, "quality_report_url": "https://example.com/report/sup009", "is_blacklisted": False},
    {"name": "安盾防护用品有限公司", "code": "SUP010", "contact": "冯经理", "phone": "13800138010", "address": "吉林省长春市宽城区防护路707号", "license_no": "91220100MA01234567", "license_url": "https://example.com/license/sup010", "credit_score": 93.0, "quality_report_url": "https://example.com/report/sup010", "is_blacklisted": False},
    {"name": "米乐食品加工有限公司", "code": "SUP011", "contact": "陈经理", "phone": "13800138011", "address": "吉林省长春市南关区食品路808号", "license_no": "91220100MA11234567", "license_url": "https://example.com/license/sup011", "credit_score": 80.5, "quality_report_url": "https://example.com/report/sup011", "is_blacklisted": False},
    {"name": "益康医疗科技有限公司", "code": "SUP012", "contact": "褚经理", "phone": "13800138012", "address": "吉林省长春市朝阳区医疗路909号", "license_no": "91220100MA22345678", "license_url": "https://example.com/license/sup012", "credit_score": 88.0, "quality_report_url": "https://example.com/report/sup012", "is_blacklisted": False},
    {"name": "乐活办公用品配送有限公司", "code": "SUP013", "contact": "卫经理", "phone": "13800138013", "address": "吉林省长春市绿园区乐活路1010号", "license_no": "91220100MA33456789", "license_url": "https://example.com/license/sup013", "credit_score": 86.5, "quality_report_url": "https://example.com/report/sup013", "is_blacklisted": False},
    {"name": "精科实验器材有限公司", "code": "SUP014", "contact": "蒋经理", "phone": "13800138014", "address": "吉林省长春市二道区精科路1111号", "license_no": "91220100MA44567890", "license_url": "https://example.com/license/sup014", "credit_score": 90.5, "quality_report_url": "https://example.com/report/sup014", "is_blacklisted": False},
    {"name": "五谷丰登粮油贸易有限公司", "code": "SUP015", "contact": "沈经理", "phone": "13800138015", "address": "吉林省长春市宽城区五谷路1212号", "license_no": "91220100MA55678901", "license_url": "https://example.com/license/sup015", "credit_score": 83.0, "quality_report_url": "https://example.com/report/sup015", "is_blacklisted": False},
    {"name": "净美消毒科技有限公司", "code": "SUP016", "contact": "韩经理", "phone": "13800138016", "address": "吉林省长春市南关区净美路1313号", "license_no": "91220100MA66789012", "license_url": "https://example.com/license/sup016", "credit_score": 89.0, "quality_report_url": "https://example.com/report/sup016", "is_blacklisted": False},
    {"name": "真彩文具用品有限公司", "code": "SUP017", "contact": "杨经理", "phone": "13800138017", "address": "吉林省长春市朝阳区真彩路1414号", "license_no": "91220100MA77890123", "license_url": "https://example.com/license/sup017", "credit_score": 91.5, "quality_report_url": "https://example.com/report/sup017", "is_blacklisted": False},
    {"name": "奥克实验设备制造有限公司", "code": "SUP018", "contact": "朱经理", "phone": "13800138018", "address": "吉林省长春市绿园区奥克路1515号", "license_no": "91220100MA88901234", "license_url": "https://example.com/license/sup018", "credit_score": 87.0, "quality_report_url": "https://example.com/report/sup018", "is_blacklisted": False},
    {"name": "绿鲜生果蔬有限公司", "code": "SUP019", "contact": "秦经理", "phone": "13800138019", "address": "吉林省长春市二道区绿鲜生路1616号", "license_no": "91220100MA99012345", "license_url": "https://example.com/license/sup019", "credit_score": 85.0, "quality_report_url": "https://example.com/report/sup019", "is_blacklisted": False},
    {"name": "瑞康防护装备有限公司", "code": "SUP020", "contact": "尤经理", "phone": "13800138020", "address": "吉林省长春市宽城区瑞康路1717号", "license_no": "91220100MA00123456", "license_url": "https://example.com/license/sup020", "credit_score": 92.5, "quality_report_url": "https://example.com/report/sup020", "is_blacklisted": False},
    {"name": "香满园食品有限公司", "code": "SUP021", "contact": "许经理", "phone": "13800138021", "address": "吉林省长春市南关区香满园路1818号", "license_no": "91220100MA11123456", "license_url": "https://example.com/license/sup021", "credit_score": 81.5, "quality_report_url": "https://example.com/report/sup021", "is_blacklisted": False},
    {"name": "健安医疗用品有限公司", "code": "SUP022", "contact": "何经理", "phone": "13800138022", "address": "吉林省长春市朝阳区健安路1919号", "license_no": "91220100MA22234567", "license_url": "https://example.com/license/sup022", "credit_score": 88.5, "quality_report_url": "https://example.com/report/sup022", "is_blacklisted": False},
    {"name": "博文办公设备有限公司", "code": "SUP023", "contact": "吕经理", "phone": "13800138023", "address": "吉林省长春市绿园区博文路2020号", "license_no": "91220100MA33345678", "license_url": "https://example.com/license/sup023", "credit_score": 86.0, "quality_report_url": "https://example.com/report/sup023", "is_blacklisted": False},
    {"name": "诺信实验仪器有限公司", "code": "SUP024", "contact": "施经理", "phone": "13800138024", "address": "吉林省长春市二道区诺信路2121号", "license_no": "91220100MA44456789", "license_url": "https://example.com/license/sup024", "credit_score": 90.0, "quality_report_url": "https://example.com/report/sup024", "is_blacklisted": False},
    {"name": "粮满仓粮油有限公司", "code": "SUP025", "contact": "张经理", "phone": "13800138025", "address": "吉林省长春市宽城区粮满仓路2222号", "license_no": "91220100MA55567890", "license_url": "https://example.com/license/sup025", "credit_score": 82.5, "quality_report_url": "https://example.com/report/sup025", "is_blacklisted": False},
    {"name": "洁宜佳消毒用品有限公司", "code": "SUP026", "contact": "孔经理", "phone": "13800138026", "address": "吉林省长春市南关区洁宜佳路2323号", "license_no": "91220100MA66678901", "license_url": "https://example.com/license/sup026", "credit_score": 89.5, "quality_report_url": "https://example.com/report/sup026", "is_blacklisted": False},
    {"name": "齐心文具制造有限公司", "code": "SUP027", "contact": "曹经理", "phone": "13800138027", "address": "吉林省长春市朝阳区齐心路2424号", "license_no": "91220100MA77789012", "license_url": "https://example.com/license/sup027", "credit_score": 91.0, "quality_report_url": "https://example.com/report/sup027", "is_blacklisted": False},
    {"name": "华测实验设备有限公司", "code": "SUP028", "contact": "严经理", "phone": "13800138028", "address": "吉林省长春市绿园区华测路2525号", "license_no": "91220100MA88890123", "license_url": "https://example.com/license/sup028", "credit_score": 87.5, "quality_report_url": "https://example.com/report/sup028", "is_blacklisted": False},
    {"name": "鲜优果蔬配送有限公司", "code": "SUP029", "contact": "华经理", "phone": "13800138029", "address": "吉林省长春市二道区鲜优路2626号", "license_no": "91220100MA99901234", "license_url": "https://example.com/license/sup029", "credit_score": 84.5, "quality_report_url": "https://example.com/report/sup029", "is_blacklisted": False},
    {"name": "恒安防护用品有限公司", "code": "SUP030", "contact": "金经理", "phone": "13800138030", "address": "吉林省长春市宽城区恒安路2727号", "license_no": "91220100MA00012345", "license_url": "https://example.com/license/sup030", "credit_score": 93.5, "quality_report_url": "https://example.com/report/sup030", "is_blacklisted": False},
    {"name": "味美食品加工有限公司", "code": "SUP031", "contact": "魏经理", "phone": "13800138031", "address": "吉林省长春市南关区味美路2828号", "license_no": "91220100MA11112345", "license_url": "https://example.com/license/sup031", "credit_score": 80.0, "quality_report_url": "https://example.com/report/sup031", "is_blacklisted": True},
    {"name": "康泰医疗设备有限公司", "code": "SUP032", "contact": "陶经理", "phone": "13800138032", "address": "吉林省长春市朝阳区康泰路2929号", "license_no": "91220100MA22223456", "license_url": "https://example.com/license/sup032", "credit_score": 88.0, "quality_report_url": "https://example.com/report/sup032", "is_blacklisted": False},
    {"name": "乐优办公用品有限公司", "code": "SUP033", "contact": "姜经理", "phone": "13800138033", "address": "吉林省长春市绿园区乐优路3030号", "license_no": "91220100MA33334567", "license_url": "https://example.com/license/sup033", "credit_score": 86.5, "quality_report_url": "https://example.com/report/sup033", "is_blacklisted": False},
    {"name": "精仪实验器材有限公司", "code": "SUP034", "contact": "戚经理", "phone": "13800138034", "address": "吉林省长春市二道区精仪路3131号", "license_no": "91220100MA44445678", "license_url": "https://example.com/license/sup034", "credit_score": 90.5, "quality_report_url": "https://example.com/report/sup034", "is_blacklisted": False},
    {"name": "金谷粮油贸易有限公司", "code": "SUP035", "contact": "谢经理", "phone": "13800138035", "address": "吉林省长春市宽城区金谷路3232号", "license_no": "91220100MA55556789", "license_url": "https://example.com/license/sup035", "credit_score": 83.5, "quality_report_url": "https://example.com/report/sup035", "is_blacklisted": False},
    {"name": "净康消毒科技有限公司", "code": "SUP036", "contact": "邹经理", "phone": "13800138036", "address": "吉林省长春市南关区净康路3333号", "license_no": "91220100MA66667890", "license_url": "https://example.com/license/sup036", "credit_score": 89.0, "quality_report_url": "https://example.com/report/sup036", "is_blacklisted": False},
    {"name": "彩星文具用品有限公司", "code": "SUP037", "contact": "喻经理", "phone": "13800138037", "address": "吉林省长春市朝阳区彩星路3434号", "license_no": "91220100MA77778901", "license_url": "https://example.com/license/sup037", "credit_score": 91.5, "quality_report_url": "https://example.com/report/sup037", "is_blacklisted": False},
    {"name": "奥普实验设备制造有限公司", "code": "SUP038", "contact": "柏经理", "phone": "13800138038", "address": "吉林省长春市绿园区奥普路3535号", "license_no": "91220100MA88889012", "license_url": "https://example.com/license/sup038", "credit_score": 87.0, "quality_report_url": "https://example.com/report/sup038", "is_blacklisted": False},
    {"name": "绿康果蔬有限公司", "code": "SUP039", "contact": "水经理", "phone": "13800138039", "address": "吉林省长春市二道区绿康路3636号", "license_no": "91220100MA99990123", "license_url": "https://example.com/license/sup039", "credit_score": 85.0, "quality_report_url": "https://example.com/report/sup039", "is_blacklisted": False},
    {"name": "瑞泰防护装备有限公司", "code": "SUP040", "contact": "窦经理", "phone": "13800138040", "address": "吉林省长春市宽城区瑞泰路3737号", "license_no": "91220100MA00001234", "license_url": "https://example.com/license/sup040", "credit_score": 92.5, "quality_report_url": "https://example.com/report/sup040", "is_blacklisted": False},
    {"name": "美味佳食品有限公司", "code": "SUP041", "contact": "章经理", "phone": "13800138041", "address": "吉林省长春市南关区美味佳路3838号", "license_no": "91220100MA11111234", "license_url": "https://example.com/license/sup041", "credit_score": 81.0, "quality_report_url": "https://example.com/report/sup041", "is_blacklisted": False},
    {"name": "健乐医疗用品有限公司", "code": "SUP042", "contact": "云经理", "phone": "13800138042", "address": "吉林省长春市朝阳区健乐路3939号", "license_no": "91220100MA22222345", "license_url": "https://example.com/license/sup042", "credit_score": 88.5, "quality_report_url": "https://example.com/report/sup042", "is_blacklisted": False},
    {"name": "博优办公设备有限公司", "code": "SUP043", "contact": "苏经理", "phone": "13800138043", "address": "吉林省长春市绿园区博优路4040号", "license_no": "91220100MA33333456", "license_url": "https://example.com/license/sup043", "credit_score": 86.0, "quality_report_url": "https://example.com/report/sup043", "is_blacklisted": False},
    {"name": "诺诚实验仪器有限公司", "code": "SUP044", "contact": "潘经理", "phone": "13800138044", "address": "吉林省长春市二道区诺诚路4141号", "license_no": "91220100MA44444567", "license_url": "https://example.com/license/sup044", "credit_score": 90.0, "quality_report_url": "https://example.com/report/sup044", "is_blacklisted": False},
    {"name": "粮丰粮油有限公司", "code": "SUP045", "contact": "葛经理", "phone": "13800138045", "address": "吉林省长春市宽城区粮丰路4242号", "license_no": "91220100MA55555678", "license_url": "https://example.com/license/sup045", "credit_score": 82.0, "quality_report_url": "https://example.com/report/sup045", "is_blacklisted": False},
    {"name": "洁丽雅消毒用品有限公司", "code": "SUP046", "contact": "奚经理", "phone": "13800138046", "address": "吉林省长春市南关区洁丽雅路4343号", "license_no": "91220100MA66666789", "license_url": "https://example.com/license/sup046", "credit_score": 89.5, "quality_report_url": "https://example.com/report/sup046", "is_blacklisted": False},
    {"name": "协力文具制造有限公司", "code": "SUP047", "contact": "范经理", "phone": "13800138047", "address": "吉林省长春市朝阳区协力路4444号", "license_no": "91220100MA77777890", "license_url": "https://example.com/license/sup047", "credit_score": 91.0, "quality_report_url": "https://example.com/report/sup047", "is_blacklisted": False},
    {"name": "华瑞实验设备有限公司", "code": "SUP048", "contact": "彭经理", "phone": "13800138048", "address": "吉林省长春市绿园区华瑞路4545号", "license_no": "91220100MA88888901", "license_url": "https://example.com/license/sup048", "credit_score": 87.5, "quality_report_url": "https://example.com/report/sup048", "is_blacklisted": False},
    {"name": "鲜乐果蔬配送有限公司", "code": "SUP049", "contact": "郎经理", "phone": "13800138049", "address": "吉林省长春市二道区鲜乐路4646号", "license_no": "91220100MA99999012", "license_url": "https://example.com/license/sup049", "credit_score": 84.0, "quality_report_url": "https://example.com/report/sup049", "is_blacklisted": False},
    {"name": "恒泰防护用品有限公司", "code": "SUP050", "contact": "鲁经理", "phone": "13800138050", "address": "吉林省长春市宽城区恒泰路4747号", "license_no": "91220100MA00000123", "license_url": "https://example.com/license/sup050", "credit_score": 93.0, "quality_report_url": "https://example.com/report/sup050", "is_blacklisted": False},
]

# 50 种物资
GOODS = [
    {"name": "东北大米", "category": "食材", "spec": "10kg/袋", "unit": "袋", "shelf_life_days": 365, "safety_level": "medium", "health_standard": '{"pesticide_residue": "合格", "moisture_content": "≤14.5%"}', "description": "优质东北大米，颗粒饱满", "is_active": True},
    {"name": "小麦面粉", "category": "食材", "spec": "5kg/袋", "unit": "袋", "shelf_life_days": 180, "safety_level": "medium", "health_standard": '{"gluten_content": "中筋", "additive_free": "是"}', "description": "家用小麦粉，适合面食制作", "is_active": True},
    {"name": "大豆油", "category": "食材", "spec": "5L/桶", "unit": "桶", "shelf_life_days": 540, "safety_level": "medium", "health_standard": '{"trans_fat": "0g", "vitamin_e": "≥15mg/100g"}', "description": "一级大豆油，健康烹饪", "is_active": True},
    {"name": "鲜鸡蛋", "category": "食材", "spec": "30枚/盒", "unit": "盒", "shelf_life_days": 45, "safety_level": "high", "health_standard": '{"salmonella": "未检出", "weight_per_egg": "50±5g"}', "description": "新鲜土鸡蛋，营养丰富", "is_active": True},
    {"name": "纯牛奶", "category": "食材", "spec": "1L/盒", "unit": "盒", "shelf_life_days": 180, "safety_level": "medium", "health_standard": '{"protein": "≥3.2g/100ml", "fat": "3.5g/100ml"}', "description": "全脂纯牛奶，早餐必备", "is_active": True},
    {"name": "大白菜", "category": "食材", "spec": "1kg/棵", "unit": "棵", "shelf_life_days": 30, "safety_level": "low", "health_standard": '{"pesticide_residue": "合格", "freshness": "一级"}', "description": "新鲜大白菜，脆嫩多汁", "is_active": True},
    {"name": "胡萝卜", "category": "食材", "spec": "500g/袋", "unit": "袋", "shelf_life_days": 45, "safety_level": "low", "health_standard": '{"beta_carotene": "≥4mg/100g", "soil_removed": "是"}', "description": "新鲜胡萝卜，富含维生素", "is_active": True},
    {"name": "土豆", "category": "食材", "spec": "2kg/袋", "unit": "袋", "shelf_life_days": 60, "safety_level": "low", "health_standard": '{"starch_content": "17-20%", "sprout_free": "是"}', "description": "黄心土豆，软糯香甜", "is_active": True},
    {"name": "西红柿", "category": "食材", "spec": "1kg/盒", "unit": "盒", "shelf_life_days": 15, "safety_level": "medium", "health_standard": '{"ripeness": "8成熟", "pesticide_residue": "合格"}', "description": "沙瓤西红柿，酸甜可口", "is_active": True},
    {"name": "黄瓜", "category": "食材", "spec": "500g/捆", "unit": "捆", "shelf_life_days": 10, "safety_level": "medium", "health_standard": '{"freshness": "带刺", "pesticide_residue": "合格"}', "description": "新鲜黄瓜，清脆爽口", "is_active": True},
    {"name": "医用外科口罩", "category": "防疫", "spec": "10只/袋", "unit": "袋", "shelf_life_days": 730, "safety_level": "high", "health_standard": '{"bfe": "≥95%", "sterile": "是"}', "description": "三层防护，医用标准", "is_active": True},
    {"name": "84消毒液", "category": "防疫", "spec": "5L/桶", "unit": "桶", "shelf_life_days": 365, "safety_level": "high", "health_standard": '{"active_chlorine": "5%", "corrosion_inhibitor": "含"}', "description": "家用消毒，高效杀菌", "is_active": True},
    {"name": "一次性防护服", "category": "防疫", "spec": "1套/袋", "unit": "套", "shelf_life_days": 1095, "safety_level": "critical", "health_standard": '{"material": "PP+PE", "waterproof": "是"}', "description": "医用防护服，全身防护", "is_active": True},
    {"name": "护目镜", "category": "防疫", "spec": "1副/盒", "unit": "副", "shelf_life_days": 0, "safety_level": "high", "health_standard": '{"anti_fog": "是", "impact_resistant": "是"}', "description": "医用护目镜，防飞溅", "is_active": True},
    {"name": "丁腈手套", "category": "防疫", "spec": "100只/盒", "unit": "盒", "shelf_life_days": 730, "safety_level": "medium", "health_standard": '{"latex_free": "是", "thickness": "0.08mm"}', "description": "无粉丁腈手套，耐用防滑", "is_active": True},
    {"name": "额温枪", "category": "防疫", "spec": "1台/盒", "unit": "台", "shelf_life_days": 0, "safety_level": "medium", "health_standard": '{"accuracy": "±0.2℃", "measurement_range": "32-42℃"}', "description": "非接触式额温枪，快速测温", "is_active": True},
    {"name": "医用酒精", "category": "防疫", "spec": "500ml/瓶", "unit": "瓶", "shelf_life_days": 1095, "safety_level": "high", "health_standard": '{"alcohol_content": "75%", "sterile": "是"}', "description": "75%医用酒精，杀菌消毒", "is_active": True},
    {"name": "免洗洗手液", "category": "防疫", "spec": "500ml/瓶", "unit": "瓶", "shelf_life_days": 365, "safety_level": "medium", "health_standard": '{"alcohol_free": "否", "moisturizing": "是"}', "description": "杀菌免洗，便携易用", "is_active": True},
    {"name": "消毒湿巾", "category": "防疫", "spec": "80抽/包", "unit": "包", "shelf_life_days": 730, "safety_level": "medium", "health_standard": '{"alcohol_content": "75%", "skin_friendly": "是"}', "description": "便携消毒湿巾，随取随用", "is_active": True},
    {"name": "防护面罩", "category": "防疫", "spec": "1个/袋", "unit": "个", "shelf_life_days": 0, "safety_level": "high", "health_standard": '{"anti_fog": "是", "full_coverage": "是"}', "description": "医用防护面罩，全面防护", "is_active": True},
    {"name": "A4复印纸", "category": "办公", "spec": "500张/包", "unit": "包", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"whiteness": "85%", "grammage": "70g/㎡"}', "description": "高白度A4纸，打印清晰", "is_active": True},
    {"name": "中性签字笔", "category": "办公", "spec": "12支/盒", "unit": "支", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"ink_color": "黑色", "tip_size": "0.5mm"}', "description": "流畅书写，不断墨", "is_active": True},
    {"name": "螺旋装订笔记本", "category": "办公", "spec": "1本/册", "unit": "本", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"pages": "100页", "size": "A5"}', "description": "便携笔记本，记录随心", "is_active": True},
    {"name": "塑料文件夹", "category": "办公", "spec": "10个/包", "unit": "个", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"material": "PP", "color": "蓝色"}', "description": "A4文件夹，整理文件", "is_active": True},
    {"name": "订书机", "category": "办公", "spec": "1台/盒", "unit": "台", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"staple_size": "24/6", "capacity": "20页"}', "description": "省力订书机，装订轻松", "is_active": True},
    {"name": "黑色打印机墨盒", "category": "办公", "spec": "1个/盒", "unit": "个", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"yield": "1500页", "compatibility": "通用型"}', "description": "喷墨打印机墨盒，打印清晰", "is_active": True},
    {"name": "回形针", "category": "办公", "spec": "100枚/盒", "unit": "枚", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"material": "镀锌铁", "size": "28mm"}', "description": "防锈回形针，固定文件", "is_active": True},
    {"name": "便利贴", "category": "办公", "spec": "100张/本", "unit": "本", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"size": "76*76mm", "color": "黄色"}', "description": "可粘贴便利贴，提醒备忘", "is_active": True},
    {"name": "文件夹板", "category": "办公", "spec": "1个/袋", "unit": "个", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"material": "ABS", "size": "A4"}', "description": "书写文件夹板，方便记录", "is_active": True},
    {"name": "太阳能计算器", "category": "办公", "spec": "1台/盒", "unit": "台", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"display": "12位", "power": "太阳能+电池"}', "description": "桌面计算器，计算精准", "is_active": True},
    {"name": "玻璃试管", "category": "实验", "spec": "10支/盒", "unit": "支", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"material": "硼硅玻璃", "size": "15*150mm"}', "description": "耐高温试管，实验专用", "is_active": True},
    {"name": "玻璃烧杯", "category": "实验", "spec": "1个/盒", "unit": "个", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"material": "硼硅玻璃", "capacity": "500ml"}', "description": "刻度烧杯，实验必备", "is_active": True},
    {"name": "酒精灯", "category": "实验", "spec": "1台/盒", "unit": "台", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"material": "玻璃", "capacity": "150ml"}', "description": "玻璃酒精灯，加热实验", "is_active": True},
    {"name": "生物显微镜", "category": "实验", "spec": "1台/箱", "unit": "台", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"magnification": "40-1600X", "light_source": "LED"}', "description": "学生用显微镜，观察微观世界", "is_active": True},
    {"name": "pH试纸", "category": "实验", "spec": "1本/盒", "unit": "本", "shelf_life_days": 0, "safety_level": "high", "health_standard": '{"range": "1-14", "accuracy": "0.5pH"}', "description": "广泛pH试纸，快速检测", "is_active": True},
    {"name": "棕色试剂瓶", "category": "实验", "spec": "1个/盒", "unit": "个", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"material": "硼硅玻璃", "capacity": "250ml"}', "description": "避光试剂瓶，保存试剂", "is_active": True},
    {"name": "胶头滴管", "category": "实验", "spec": "10支/包", "unit": "支", "shelf_life_days": 0, "safety_level": "high", "health_standard": '{"material": "玻璃+橡胶", "capacity": "1ml"}', "description": "刻度胶头滴管，精确移液", "is_active": True},
    {"name": "玻璃棒", "category": "实验", "spec": "5支/包", "unit": "支", "shelf_life_days": 0, "safety_level": "high", "health_standard": '{"material": "硼硅玻璃", "length": "200mm"}', "description": "搅拌玻璃棒，实验工具", "is_active": True},
    {"name": "塑料培养皿", "category": "实验", "spec": "10个/包", "unit": "个", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"material": "PS", "diameter": "90mm"}', "description": "无菌培养皿，微生物培养", "is_active": True},
    {"name": "电子天平", "category": "实验", "spec": "1台/箱", "unit": "台", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"accuracy": "0.01g", "capacity": "200g"}', "description": "精密电子天平，准确称量", "is_active": True},
    {"name": "圆白菜", "category": "食材", "spec": "1kg/棵", "unit": "棵", "shelf_life_days": 30, "safety_level": "low", "health_standard": '{"pesticide_residue": "合格", "freshness": "一级"}', "description": "新鲜圆白菜，营养丰富", "is_active": True},
    {"name": "洋葱", "category": "食材", "spec": "1kg/袋", "unit": "袋", "shelf_life_days": 60, "safety_level": "low", "health_standard": '{"pungency": "中等", "soil_removed": "是"}', "description": "黄皮洋葱，辛辣提味", "is_active": True},
    {"name": "苹果", "category": "食材", "spec": "1kg/盒", "unit": "盒", "shelf_life_days": 30, "safety_level": "medium", "health_standard": '{"variety": "红富士", "pesticide_residue": "合格"}', "description": "新鲜红富士苹果，脆甜多汁", "is_active": True},
    {"name": "香蕉", "category": "食材", "spec": "1kg/串", "unit": "串", "shelf_life_days": 7, "safety_level": "medium", "health_standard": '{"ripeness": "7成熟", "origin": "海南"}', "description": "新鲜香蕉，香甜软糯", "is_active": True},
    {"name": "医用手套", "category": "防疫", "spec": "100只/盒", "unit": "盒", "shelf_life_days": 730, "safety_level": "high", "health_standard": '{"material": "乳胶", "powder_free": "否"}', "description": "医用乳胶手套，贴合双手", "is_active": True},
    {"name": "碘伏", "category": "防疫", "spec": "500ml/瓶", "unit": "瓶", "shelf_life_days": 1095, "safety_level": "high", "health_standard": '{"active_ingredient": "0.5%聚维酮碘", "sterile": "是"}', "description": "医用碘伏消毒液，温和杀菌", "is_active": True},
    {"name": "荧光笔", "category": "办公", "spec": "10支/盒", "unit": "支", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"ink_color": "黄色/粉色/绿色", "tip_size": "斜头"}', "description": "彩色荧光笔，标记重点", "is_active": True},
    {"name": "修正带", "category": "办公", "spec": "5个/盒", "unit": "个", "shelf_life_days": 0, "safety_level": "low", "health_standard": '{"width": "5mm", "length": "6m"}', "description": "顺滑修正带，修改错误", "is_active": True},
    {"name": "漏斗", "category": "实验", "spec": "1个/盒", "unit": "个", "shelf_life_days": 0, "safety_level": "high", "health_standard": '{"material": "玻璃", "diameter": "75mm"}', "description": "三角漏斗，过滤液体", "is_active": True},
    {"name": "量筒", "category": "实验", "spec": "1个/盒", "unit": "个", "shelf_life_days": 0, "safety_level": "critical", "health_standard": '{"material": "硼硅玻璃", "capacity": "100ml"}', "description": "刻度量筒，量取液体", "is_active": True},
]

def main():
    # 供应商：按名称去重，已存在则跳过
    for s in SUPPLIERS:
        if not db.query(Supplier).filter(Supplier.name == s["name"]).first():
            db.add(Supplier(**s))

    # 物资：按名称去重
    for g in GOODS:
        if not db.query(Goods).filter(Goods.name == g["name"]).first():
            db.add(Goods(**g))

    db.commit()
    print(f"导入完成：{len(SUPPLIERS)} 家供应商，{len(GOODS)} 种物资")

if __name__ == "__main__":
    main()
    db.close()
