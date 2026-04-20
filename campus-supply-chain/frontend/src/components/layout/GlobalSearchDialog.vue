<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Search } from '@element-plus/icons-vue'
import { openSearchBus } from '@/utils/layoutBus'
import { getFlattenedMenuRoutes } from '@/utils/menuFlatten'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const visible = ref(false)
const q = ref('')
const activeIndex = ref(0)

const allItems = computed(() => getFlattenedMenuRoutes())

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return []
  return allItems.value.filter(
    (x) => x.title.toLowerCase().includes(s) || x.path.toLowerCase().includes(s)
  )
})

const historyPaths = computed(() => userStore.searchHistory)

const historyItems = computed(() => {
  const map = new Map(allItems.value.map((x) => [x.path, x]))
  return historyPaths.value.map((p) => map.get(p)).filter(Boolean) as { path: string; title: string }[]
})

const list = computed(() => (q.value.trim() ? filtered.value : historyItems.value))

const isWindows = typeof navigator !== 'undefined' && navigator.userAgent.includes('Windows')

watch(visible, (v) => {
  if (v) {
    q.value = ''
    activeIndex.value = 0
    requestAnimationFrame(() => {
      const el = document.querySelector('.global-search-dialog input') as HTMLInputElement | null
      el?.focus()
    })
  }
})

watch(list, () => {
  activeIndex.value = 0
})

function go(item: { path: string }) {
  userStore.pushSearchHistory(item.path)
  visible.value = false
  router.push(item.path)
}

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    visible.value = true
  }
  if (!visible.value) return
  if (e.key === 'Escape') {
    e.preventDefault()
    visible.value = false
  }
  if (e.key === 'ArrowDown' && list.value.length) {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % list.value.length
  }
  if (e.key === 'ArrowUp' && list.value.length) {
    e.preventDefault()
    activeIndex.value = (activeIndex.value - 1 + list.value.length) % list.value.length
  }
  if (e.key === 'Enter' && list.value.length) {
    e.preventDefault()
    go(list.value[activeIndex.value])
  }
}

let unsub: (() => void) | undefined

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  unsub = openSearchBus.on(() => {
    visible.value = true
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  unsub?.()
})
</script>

<template>
  <el-dialog
    v-model="visible"
    class="global-search-dialog"
    width="560px"
    :show-close="true"
    append-to-body
    destroy-on-close
    @closed="q = ''"
  >
    <template #header>
      <div class="gs-head">
        <el-input
          v-model="q"
          :placeholder="t('search.placeholder')"
          clearable
          size="large"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
    </template>
    <div class="gs-hint">
      <span>{{ t('search.selectKeydown') }}</span>
      <span>{{ t('search.switchKeydown') }}</span>
      <span>{{ t('search.exitKeydown') }}</span>
    </div>
    <el-scrollbar max-height="360px">
      <p v-if="!q.trim() && historyItems.length" class="gs-section">{{ t('search.historyTitle') }}</p>
      <ul class="gs-list">
        <li
          v-for="(item, i) in list"
          :key="item.path"
          :class="{ active: i === activeIndex }"
          @click="go(item)"
          @mouseenter="activeIndex = i"
        >
          <span class="t">{{ item.title }}</span>
          <span class="p">{{ item.path }}</span>
        </li>
      </ul>
      <div v-if="!list.length" class="gs-empty">{{ t('notice.empty') }}</div>
    </el-scrollbar>
    <template #footer>
      <div class="gs-kbd">
        <span class="kbd">{{ isWindows ? 'Ctrl' : '⌘' }}</span>
        <span class="kbd">K</span>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.gs-head {
  width: 100%;
}
.gs-hint {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.gs-section {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 8px;
}
.gs-list {
  list-style: none;
  margin: 0;
  padding: 0;
  li {
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    margin-bottom: 4px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    transition: background 0.15s ease;
    .t {
      font-size: 14px;
      color: var(--text-primary);
    }
    .p {
      font-size: 12px;
      color: var(--text-muted);
    }
    &:hover,
    &.active {
      background: var(--primary-muted);
    }
  }
}
.gs-empty {
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
  font-size: 13px;
}
.gs-kbd {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  .kbd {
    font-size: 11px;
    padding: 2px 6px;
    border: 1px solid var(--border-default);
    border-radius: 4px;
    color: var(--text-muted);
  }
}
</style>
