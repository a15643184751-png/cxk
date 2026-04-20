/**
 * Mock Server - 轻量本地替身，支撑 AI 对话与执行接口联调
 * 流程：自然语言 → React 推理 → 决策 → 执行 → 留痕 → 存入记忆
 */
const http = require('http')

const PORT = 5200

// 固定触发词：匹配此类问题返回完整闭环响应
const DEMO_TRIGGERS = ['短缺', '补货', '缺什么', '需要补', '什么缺少', '可能短缺']
const isDemoQuestion = (q) => DEMO_TRIGGERS.some((t) => q.includes(t))

// 预置固定响应
const DEMO_CHAT_RESPONSE = {
  code: 200,
  data: {
    reply: `根据库存与消耗趋势分析，结论如下：

【即将短缺】
• 大米（粳米 25kg）：库存约 3 天用量，建议 2 日内补货
• 食用油（5L 桶）：低于安全库存，建议立即补货

【建议提前预备】
• 面粉：下周有活动，建议本周内增加备货

点击下方「创建采购单」可一键生成补货申请。`,
    react: [
      { step: 1, text: '解析用户意图：查询短缺物资及补货建议' },
      { step: 2, text: '调用数据仓库：读取库存、安全库存、近7天消耗' },
      { step: 3, text: '计算短缺风险：大米、食用油低于安全线；面粉需提前预备' },
      { step: 4, text: '生成决策建议：3 项补货，1 项预备' },
    ],
    actions: [
      {
        type: 'create_purchase',
        label: '创建采购单',
        payload: {
          items: [
            { name: '大米 25kg', quantity: 50, unit: '袋' },
            { name: '食用油 5L', quantity: 20, unit: '桶' },
            { name: '面粉', quantity: 30, unit: '袋' },
          ],
        },
      },
    ],
  },
}

const DEMO_OTHER_RESPONSE = {
  code: 200,
  data: {
    reply: '可尝试输入：\n「现在什么物资可能短缺？需要补货吗？」\n将返回完整链路：React 推理 → 决策建议 → 执行 → 留痕 → 存入记忆。',
    react: [],
    actions: [],
  },
}

// 执行后返回（留痕 + 记忆）
const executeResponse = (payload) => ({
  code: 200,
  data: {
    success: true,
    orderNo: `PO${Date.now().toString().slice(-8)}`,
    trace: {
      action: 'create_purchase',
      executedAt: new Date().toISOString(),
      items: payload?.items || [],
    },
    memorySaved: true,
  },
})

const server = http.createServer((req, res) => {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  }

  if (req.method === 'OPTIONS') {
    res.writeHead(204, cors)
    res.end()
    return
  }

  let body = ''
  req.on('data', (chunk) => (body += chunk))
  req.on('end', () => {
    const url = req.url
    const method = req.method

    const send = (data, status = 200) => {
      res.writeHead(status, { ...cors, 'Content-Type': 'application/json' })
      res.end(JSON.stringify(data))
    }

    if (url === '/api/ai/chat' && method === 'POST') {
      const { message } = JSON.parse(body || '{}')
      const resp = isDemoQuestion(message || '') ? DEMO_CHAT_RESPONSE : DEMO_OTHER_RESPONSE
      send(resp)
      return
    }

    if (url === '/api/ai/execute' && method === 'POST') {
      const { type, payload } = JSON.parse(body || '{}')
      if (type === 'create_purchase') {
        send(executeResponse(payload))
      } else {
        send({ code: 200, data: { success: true } })
      }
      return
    }

    send({ code: 404, message: 'Not Found' }, 404)
  })
})

server.listen(PORT, () => {
  console.log(`[Mock Server] http://127.0.0.1:${PORT}`)
  console.log(`  - POST /api/ai/chat  示例：现在什么物资可能短缺？需要补货吗？`)
  console.log(`  - POST /api/ai/execute`)
})
