<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Connection, Link, Lock, Monitor, Promotion, RefreshRight } from '@element-plus/icons-vue'
import { getIDSBridgeStatus, type IDSBridgeStatusResponse } from '@/api/ids'

const loading = ref(true)
const bridge = ref<IDSBridgeStatusResponse | null>(null)

const linkageCards = computed(() => {
  if (!bridge.value) return []
  return [
    {
      key: 'anfu',
      title: '安全工作台',
      subtitle: '发起侦察任务、跟踪过程日志并整理验证结果。',
      url: bridge.value.anfu_console_url,
      accent: 'orange',
      icon: Promotion,
    },
    {
      key: 'site',
      title: '校园供应链',
      subtitle: '作为目标站点承载业务访问，并在本地识别和拦截异常请求。',
      url: bridge.value.site_console_url,
      accent: 'blue',
      icon: Monitor,
    },
    {
      key: 'ids',
      title: '安全分析中心',
      subtitle: '统一归集风险事件、样本审计、AI 研判与验证结论。',
      url: bridge.value.standalone_console_url || bridge.value.standalone_api_url,
      accent: 'green',
      icon: Lock,
    },
  ]
})

async function loadBridge() {
  loading.value = true
  try {
    bridge.value = await getIDSBridgeStatus()
  } finally {
    loading.value = false
  }
}

function openUrl(url: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  loadBridge()
})
</script>

<template>
  <div class="security-linkage" v-loading="loading">
    <section class="hero">
      <div class="hero-copy">
        <div class="hero-badge">
          <el-icon><Connection /></el-icon>
          <span>攻防验证入口</span>
        </div>
        <h1>当前站点已接入统一验证链路</h1>
        <p>
          当前页面用于查看站点桥接状态、节点连通性与验证入口。
          校园供应链作为目标站点继续承载业务访问，异常请求与送检样本会同步进入安全分析中心，便于复核渗透验证结果。
        </p>
      </div>
      <button class="refresh-btn" @click="loadBridge">
        <el-icon><RefreshRight /></el-icon>
        <span>刷新状态</span>
      </button>
    </section>

    <section class="status-grid">
      <article class="status-card">
        <div class="status-head">
          <span class="status-title">主站桥接状态</span>
          <span class="status-pill" :class="bridge?.bridge_enabled ? 'ok' : 'warn'">
            {{ bridge?.bridge_enabled ? '已启用' : '未启用' }}
          </span>
        </div>
        <div class="status-body">
          <div class="status-row">
            <span>分析中心基址</span>
            <strong>{{ bridge?.standalone_base_url || '-' }}</strong>
          </div>
          <div class="status-row">
            <span>来源标识</span>
            <strong>{{ bridge?.source_system || '-' }}</strong>
          </div>
          <div class="status-row">
            <span>共享令牌</span>
            <strong>{{ bridge?.token_configured ? '已配置' : '未配置' }}</strong>
          </div>
        </div>
      </article>

      <article class="status-card">
        <div class="status-head">
          <span class="status-title">分析中心健康探测</span>
          <span class="status-pill" :class="bridge?.health?.ok ? 'ok' : 'warn'">
            {{ bridge?.health?.ok ? '在线' : '待检查' }}
          </span>
        </div>
        <div class="status-body">
          <div class="status-row">
            <span>状态码</span>
            <strong>{{ bridge?.health?.status_code ?? '-' }}</strong>
          </div>
          <div class="status-row">
            <span>说明</span>
            <strong>{{ bridge?.health?.ok ? '桥接正常' : '请检查分析中心服务' }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="cards">
      <article
        v-for="card in linkageCards"
        :key="card.key"
        class="link-card"
        :class="`link-card--${card.accent}`"
      >
        <div class="link-card__icon">
          <el-icon><component :is="card.icon" /></el-icon>
        </div>
        <div class="link-card__copy">
          <h3>{{ card.title }}</h3>
          <p>{{ card.subtitle }}</p>
          <code>{{ card.url }}</code>
        </div>
        <button class="link-card__btn" @click="openUrl(card.url)">
          <span>打开</span>
          <el-icon><Link /></el-icon>
        </button>
      </article>
    </section>

    <section class="flow-card">
      <div class="flow-card__head">验证链路</div>
      <div class="flow">
        <div class="flow-node">
          <strong>1. 安全工作台</strong>
          <span>发起侦察任务，汇总信息收集、指纹识别与验证结果。</span>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-node">
          <strong>2. 校园供应链</strong>
          <span>承载业务页面与接口访问，站点侧策略即时识别并拦截异常请求。</span>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-node">
          <strong>3. 安全分析中心</strong>
          <span>统一接收桥接事件、文件样本、阻断结果与复核结论。</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.security-linkage {
  height: 100%;
  overflow-y: auto;
  padding: 28px;
  color: #d9e2f2;
  background:
    radial-gradient(circle at top left, rgba(25, 78, 166, 0.22), transparent 28%),
    radial-gradient(circle at top right, rgba(11, 122, 96, 0.18), transparent 24%),
    linear-gradient(180deg, #08101c 0%, #0d1524 100%);
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding: 28px 32px;
  border: 1px solid rgba(120, 146, 192, 0.18);
  border-radius: 24px;
  background: linear-gradient(145deg, rgba(10, 18, 34, 0.94), rgba(14, 24, 43, 0.9));
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(79, 142, 247, 0.14);
  border: 1px solid rgba(79, 142, 247, 0.3);
  color: #8bb7ff;
  font-size: 12px;
  margin-bottom: 14px;
}

.hero h1 {
  margin: 0 0 14px;
  font-size: 28px;
  line-height: 1.2;
  color: #f7fbff;
}

.hero p {
  margin: 0;
  max-width: 760px;
  line-height: 1.8;
  color: rgba(217, 226, 242, 0.78);
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(79, 142, 247, 0.28);
  background: rgba(79, 142, 247, 0.1);
  color: #b9d2ff;
  padding: 10px 14px;
  border-radius: 12px;
  cursor: pointer;
}

.status-grid,
.cards {
  display: grid;
  gap: 18px;
  margin-top: 22px;
}

.status-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.status-card,
.flow-card {
  border: 1px solid rgba(120, 146, 192, 0.16);
  border-radius: 18px;
  background: rgba(10, 18, 34, 0.84);
  padding: 20px 22px;
}

.status-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.status-title,
.flow-card__head {
  font-size: 14px;
  font-weight: 700;
  color: #f4f7fb;
}

.status-pill {
  font-size: 12px;
  border-radius: 999px;
  padding: 4px 10px;
  border: 1px solid transparent;
}

.status-pill.ok {
  color: #53d29c;
  background: rgba(83, 210, 156, 0.14);
  border-color: rgba(83, 210, 156, 0.28);
}

.status-pill.warn {
  color: #f7c65b;
  background: rgba(247, 198, 91, 0.12);
  border-color: rgba(247, 198, 91, 0.24);
}

.status-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  font-size: 13px;
  color: rgba(217, 226, 242, 0.72);
}

.status-row strong {
  color: #f7fbff;
  font-weight: 600;
  text-align: right;
}

.cards {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.link-card {
  border-radius: 20px;
  padding: 22px;
  border: 1px solid rgba(120, 146, 192, 0.16);
  background: rgba(10, 18, 34, 0.84);
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 240px;
}

.link-card__icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.link-card--orange .link-card__icon {
  background: rgba(247, 147, 79, 0.16);
  color: #f7934f;
}

.link-card--blue .link-card__icon {
  background: rgba(79, 142, 247, 0.16);
  color: #4f8ef7;
}

.link-card--green .link-card__icon {
  background: rgba(79, 209, 138, 0.16);
  color: #4fd18a;
}

.link-card h3 {
  margin: 0 0 8px;
  color: #f7fbff;
  font-size: 18px;
}

.link-card p {
  margin: 0 0 12px;
  color: rgba(217, 226, 242, 0.74);
  line-height: 1.7;
  min-height: 68px;
}

.link-card code {
  display: block;
  word-break: break-all;
  color: #9ec3ff;
  font-size: 12px;
}

.link-card__btn {
  margin-top: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  min-height: 42px;
  font-weight: 700;
  color: #08101c;
  background: linear-gradient(135deg, #8eb7ff, #4fd18a);
}

.flow-card {
  margin-top: 22px;
}

.flow {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 40px 1fr 40px 1fr;
  gap: 10px;
  align-items: center;
}

.flow-node {
  min-height: 120px;
  border-radius: 16px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(120, 146, 192, 0.16);
}

.flow-node strong {
  display: block;
  margin-bottom: 8px;
  color: #f7fbff;
}

.flow-node span {
  color: rgba(217, 226, 242, 0.74);
  line-height: 1.7;
}

.flow-arrow {
  text-align: center;
  color: #8bb7ff;
  font-size: 22px;
  font-weight: 800;
}

@media (max-width: 1200px) {
  .cards {
    grid-template-columns: 1fr;
  }

  .flow {
    grid-template-columns: 1fr;
  }

  .flow-arrow {
    transform: rotate(90deg);
  }
}

@media (max-width: 900px) {
  .security-linkage {
    padding: 18px;
  }

  .hero,
  .status-grid {
    grid-template-columns: 1fr;
  }

  .hero {
    flex-direction: column;
  }

  .status-grid {
    display: grid;
  }
}
</style>
