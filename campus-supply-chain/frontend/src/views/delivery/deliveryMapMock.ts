/**
 * 配送地图：徐汇校区平面示意与配送单数据
 */
export type DelStatus = 'pending' | 'on_way' | 'received' | 'exception'

export interface MockDeliveryOrder {
  id: string
  delivery_no: string
  destination: string
  receiver: string
  status: DelStatus
  handoff_code: string
  buildingId: string
  materialType: '办公' | '教学' | '实验' | '食品'
  qty: number
  signedAt: string | null
}

export interface CampusPlace {
  id: string
  name: string
  kind: 'hub' | 'admin' | 'college' | 'teach' | 'lab' | 'life' | 'sport' | 'service' | 'plaza' | 'road'
  x: number
  y: number
  w: number
  h: number
  /** 列表/弹窗短名 */
  short: string
}

/** 校园平面图画布逻辑尺寸（与 .dm-world、底图 SVG 内层坐标系一致） */
export const MAP_W = 1920
export const MAP_H = 1200

/** 底图 SVG 路径仍按 1680×1040 编写，组件内通过 scale(MAP_W/1680, MAP_H/1040) 映射到画布。 */
export const MAP_BASE_W = 1680
export const MAP_BASE_H = 1040

export const WAREHOUSE_ID = 'place-logistics-hub'

/**
 * 与 DeliveryMap.vue 中 SVG 道路对齐的「不可建筑」走廊（与 MAP 同坐标系）。
 */
export const MAP_ROAD = {
  yMain0: 542,
  yMain1: 625,
  yLow0: 752,
  yLow1: 822,
  xV10: 407,
  xV11: 466,
  xV20: 999,
  xV21: 1065,
  xV30: 1442,
  xV31: 1502,
} as const

export const campusPlaces: CampusPlace[] = [
  { id: WAREHOUSE_ID, name: '后勤物资总仓库', short: '总仓', kind: 'hub', x: 52, y: 1048, w: 142, h: 94 },
  { id: 'place-dorm1', name: '学生公寓 1 栋', short: '公寓1', kind: 'life', x: 92, y: 838, w: 92, h: 62 },
  { id: 'place-dorm2', name: '学生公寓 2 栋', short: '公寓2', kind: 'life', x: 208, y: 838, w: 92, h: 62 },
  { id: 'place-dorm3', name: '学生公寓 3 栋', short: '公寓3', kind: 'life', x: 324, y: 838, w: 92, h: 62 },
  { id: 'place-dorm4', name: '学生公寓 4 栋', short: '公寓4', kind: 'life', x: 148, y: 916, w: 92, h: 62 },
  { id: 'place-dorm5', name: '学生公寓 5 栋', short: '公寓5', kind: 'life', x: 268, y: 916, w: 92, h: 62 },
  { id: 'place-dorm6', name: '学生公寓 6 栋', short: '公寓6', kind: 'life', x: 388, y: 916, w: 92, h: 62 },
  { id: 'place-mart', name: '校园超市', short: '超市', kind: 'life', x: 518, y: 908, w: 112, h: 64 },
  { id: 'place-express', name: '快递服务站', short: '快递站', kind: 'life', x: 702, y: 902, w: 118, h: 62 },
  { id: 'place-lab-cs', name: '计算机实验室集群', short: '计科实验', kind: 'lab', x: 1008, y: 958, w: 138, h: 84 },
  { id: 'place-lab-eng', name: '工科实训中心', short: '工训', kind: 'lab', x: 1162, y: 962, w: 128, h: 82 },
  { id: 'place-lab-voice', name: '语音实验室', short: '语音室', kind: 'lab', x: 1308, y: 968, w: 104, h: 72 },
  { id: 'place-plaza', name: '校园中心广场', short: '广场', kind: 'plaza', x: 468, y: 638, w: 456, h: 102 },
  { id: 'place-logistics-svc', name: '后勤服务中心', short: '后勤中心', kind: 'service', x: 72, y: 108, w: 118, h: 72 },
  { id: 'place-security', name: '安保值班室', short: '安保', kind: 'service', x: 72, y: 198, w: 86, h: 56 },
  { id: 'place-admin', name: '综合行政楼', short: '行政楼', kind: 'admin', x: 448, y: 78, w: 112, h: 78 },
  { id: 'place-library', name: '图书馆', short: '图书馆', kind: 'admin', x: 578, y: 68, w: 138, h: 96 },
  { id: 'place-student-center', name: '大学生活动中心', short: '学生活动', kind: 'life', x: 732, y: 72, w: 124, h: 88 },
  { id: 'place-hospital', name: '校医院', short: '校医院', kind: 'service', x: 872, y: 88, w: 106, h: 70 },
  { id: 'place-canteen1', name: '第一食堂', short: '一食堂', kind: 'life', x: 998, y: 82, w: 108, h: 72 },
  { id: 'place-canteen2', name: '第二食堂', short: '二食堂', kind: 'life', x: 1122, y: 84, w: 108, h: 70 },
  { id: 'place-sports', name: '体育场馆（操场/体育馆）', short: '体育馆', kind: 'sport', x: 1388, y: 66, w: 148, h: 104 },
  { id: 'place-ie', name: '信息工程学院', short: '信工', kind: 'college', x: 432, y: 268, w: 122, h: 82 },
  { id: 'place-me', name: '机电工程学院', short: '机电', kind: 'college', x: 568, y: 264, w: 122, h: 82 },
  { id: 'place-civil', name: '建筑与土木工程学院', short: '建土', kind: 'college', x: 704, y: 268, w: 130, h: 82 },
  { id: 'place-biz', name: '商学院', short: '商学院', kind: 'college', x: 988, y: 272, w: 108, h: 78 },
  { id: 'place-lit', name: '文学院', short: '文学院', kind: 'college', x: 1108, y: 268, w: 108, h: 78 },
  { id: 'place-foreign', name: '外国语学院', short: '外语', kind: 'college', x: 1228, y: 272, w: 106, h: 78 },
  { id: 'place-law', name: '法学院', short: '法学院', kind: 'college', x: 1388, y: 278, w: 100, h: 74 },
  { id: 'place-art', name: '艺术设计学院', short: '艺设', kind: 'college', x: 1502, y: 274, w: 114, h: 78 },
  { id: 'place-med', name: '医学院', short: '医学院', kind: 'college', x: 438, y: 388, w: 108, h: 78 },
  { id: 'place-marx', name: '马克思主义学院', short: '马院', kind: 'college', x: 558, y: 392, w: 114, h: 78 },
  { id: 'place-food-bio', name: '食品与生物工程学院', short: '食生', kind: 'college', x: 686, y: 388, w: 128, h: 82 },
  { id: 'place-rail', name: '轨道交通学院', short: '轨道', kind: 'college', x: 988, y: 392, w: 122, h: 82 },
  { id: 'place-teach-a', name: '公共教学楼 A 座', short: '教学楼A', kind: 'teach', x: 1128, y: 396, w: 98, h: 70 },
  { id: 'place-teach-b', name: '公共教学楼 B 座', short: '教学楼B', kind: 'teach', x: 1242, y: 398, w: 98, h: 70 },
  { id: 'place-teach-c', name: '公共教学楼 C 座', short: '教学楼C', kind: 'teach', x: 1358, y: 402, w: 98, h: 70 },
  { id: 'place-lab-main', name: '综合实验中心', short: '实验中心', kind: 'lab', x: 1472, y: 396, w: 128, h: 84 },
]

export const mockDeliveryOrders: MockDeliveryOrder[] = [
  {
    id: 'd1',
    delivery_no: 'PS20260415001',
    destination: '信息工程学院 · 智算实验室',
    receiver: '王老师',
    status: 'on_way',
    handoff_code: 'A8K2M9',
    buildingId: 'place-ie',
    materialType: '实验',
    qty: 120,
    signedAt: null,
  },
  {
    id: 'd2',
    delivery_no: 'PS20260415002',
    destination: '第一食堂 · 后厨补给',
    receiver: '饮食中心-李师傅',
    status: 'pending',
    handoff_code: 'B3N7P1',
    buildingId: 'place-canteen1',
    materialType: '食品',
    qty: 2400,
    signedAt: null,
  },
  {
    id: 'd3',
    delivery_no: 'PS20260415003',
    destination: '公共教学楼 B 座 · 考务办',
    receiver: '教务处-张老师',
    status: 'received',
    handoff_code: 'C1Q4R8',
    buildingId: 'place-teach-b',
    materialType: '办公',
    qty: 80,
    signedAt: '2026-04-15 09:42:18',
  },
  {
    id: 'd4',
    delivery_no: 'PS20260415004',
    destination: '医学院 · 解剖学准备室',
    receiver: '实验员-赵老师',
    status: 'on_way',
    handoff_code: 'D9S2T5',
    buildingId: 'place-med',
    materialType: '实验',
    qty: 36,
    signedAt: null,
  },
  {
    id: 'd5',
    delivery_no: 'PS20260414088',
    destination: '建筑与土木工程学院 · 制图教室',
    receiver: '刘老师',
    status: 'received',
    handoff_code: 'E7U1V4',
    buildingId: 'place-civil',
    materialType: '教学',
    qty: 200,
    signedAt: '2026-04-14 16:05:33',
  },
  {
    id: 'd6',
    delivery_no: 'PS20260415006',
    destination: '轨道交通学院 · 实训车间',
    receiver: '周工',
    status: 'pending',
    handoff_code: 'F2W6X0',
    buildingId: 'place-rail',
    materialType: '教学',
    qty: 45,
    signedAt: null,
  },
  {
    id: 'd7',
    delivery_no: 'PS20260415007',
    destination: '外国语学院 · 语音室管理室',
    receiver: '陈老师',
    status: 'exception',
    handoff_code: 'G5Y8Z3',
    buildingId: 'place-foreign',
    materialType: '教学',
    qty: 60,
    signedAt: null,
  },
  {
    id: 'd8',
    delivery_no: 'PS20260415008',
    destination: '图书馆 · 密集书库',
    receiver: '馆员-小吴',
    status: 'on_way',
    handoff_code: 'H4A7B2',
    buildingId: 'place-library',
    materialType: '办公',
    qty: 500,
    signedAt: null,
  },
  {
    id: 'd9',
    delivery_no: 'PS20260415009',
    destination: '计算机实验室集群',
    receiver: '信息中心',
    status: 'pending',
    handoff_code: 'J1C6D9',
    buildingId: 'place-lab-cs',
    materialType: '实验',
    qty: 24,
    signedAt: null,
  },
  {
    id: 'd10',
    delivery_no: 'PS20260415010',
    destination: '学生公寓 3 栋 · 值班室',
    receiver: '宿管-孙阿姨',
    status: 'received',
    handoff_code: 'K8E3F7',
    buildingId: 'place-dorm3',
    materialType: '食品',
    qty: 48,
    signedAt: '2026-04-15 08:12:00',
  },
  {
    id: 'd11',
    delivery_no: 'PS20260415011',
    destination: '马克思主义学院 · 资料室',
    receiver: '邓老师',
    status: 'received',
    handoff_code: 'L2G5H1',
    buildingId: 'place-marx',
    materialType: '办公',
    qty: 160,
    signedAt: '2026-04-15 07:55:22',
  },
  {
    id: 'd12',
    delivery_no: 'PS20260415012',
    destination: '第二食堂 · 冷链收货口',
    receiver: '饮食中心-郑主管',
    status: 'on_way',
    handoff_code: 'M9I4J8',
    buildingId: 'place-canteen2',
    materialType: '食品',
    qty: 1800,
    signedAt: null,
  },
  {
    id: 'd13',
    delivery_no: 'PS20260415013',
    destination: '综合实验中心 · 危化暂存区外',
    receiver: '实验中心-钱老师',
    status: 'pending',
    handoff_code: 'N3K7L2',
    buildingId: 'place-lab-main',
    materialType: '实验',
    qty: 12,
    signedAt: null,
  },
  {
    id: 'd14',
    delivery_no: 'PS20260415014',
    destination: '公共教学楼 A 座 · 多媒体运维',
    receiver: '运维-何工',
    status: 'exception',
    handoff_code: 'O6M1N5',
    buildingId: 'place-teach-a',
    materialType: '教学',
    qty: 4,
    signedAt: null,
  },
  {
    id: 'd15',
    delivery_no: 'PS20260415015',
    destination: '快递服务站 · 大宗暂存',
    receiver: '站点-小徐',
    status: 'received',
    handoff_code: 'P4O9Q3',
    buildingId: 'place-express',
    materialType: '办公',
    qty: 320,
    signedAt: '2026-04-15 10:18:44',
  },
  {
    id: 'd16',
    delivery_no: 'PS20260415016',
    destination: '体育场馆 · 赛事保障点',
    receiver: '场馆-林主管',
    status: 'on_way',
    handoff_code: 'Q7R2S6',
    buildingId: 'place-sports',
    materialType: '食品',
    qty: 600,
    signedAt: null,
  },
  {
    id: 'd17',
    delivery_no: 'PS20260415017',
    destination: '校园超市 · 收货区',
    receiver: '店长-黄姐',
    status: 'pending',
    handoff_code: 'R1T8U4',
    buildingId: 'place-mart',
    materialType: '食品',
    qty: 900,
    signedAt: null,
  },
  {
    id: 'd18',
    delivery_no: 'PS20260415018',
    destination: '公共教学楼 C 座 · 考务材料室',
    receiver: '考务-马老师',
    status: 'received',
    handoff_code: 'S5V0W7',
    buildingId: 'place-teach-c',
    materialType: '办公',
    qty: 150,
    signedAt: '2026-04-15 11:02:09',
  },
]

export function centerOfPlace(p: CampusPlace) {
  return { cx: p.x + p.w / 2, cy: p.y + p.h / 2 }
}

export function warehouseCenter() {
  const w = campusPlaces.find((p) => p.id === WAREHOUSE_ID)!
  return centerOfPlace(w)
}
