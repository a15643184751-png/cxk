/**
 * 商品名 → 静态图（public/teacher-demo），接口未带图时兜底
 */
const KEYWORD_MAP: Array<{ keys: string[]; src: string }> = [
  { keys: ['A4', '复印纸', '打印纸'], src: '/teacher-demo/a4-paper.jpg' },
  { keys: ['水', '饮用'], src: '/teacher-demo/water.jpg' },
  { keys: ['粉笔', '白板笔', '板擦'], src: '/teacher-demo/chalk.jpg' },
  { keys: ['订书机', '起钉器'], src: '/teacher-demo/stapler.jpg' },
  { keys: ['投影'], src: '/teacher-demo/projector.jpg' },
  { keys: ['翻页笔', '激光笔'], src: '/teacher-demo/laser-pointer.jpg' },
]

export function catalogImageForGoodsName(name: string): string | undefined {
  const n = name.trim()
  for (const { keys, src } of KEYWORD_MAP) {
    if (keys.some((k) => n.includes(k))) return src
  }
  return undefined
}
