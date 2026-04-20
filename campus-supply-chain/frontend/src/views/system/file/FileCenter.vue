<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Search,
  Upload,
  Delete,
  Download,
  Link,
  FullScreen,
  Grid,
  Document,
} from '@element-plus/icons-vue'
import { useSystemManagementStore, type FileCenterRow } from '@/stores/systemManagement'
import { useUserStore } from '@/stores/user'

const store = useSystemManagementStore()
const { files } = storeToRefs(store)
const userStore = useUserStore()

const loading = ref(false)
const selected = ref<FileCenterRow[]>([])
const showFilter = ref(true)
const tableSize = ref<'large' | 'default' | 'small'>('default')
const fullscreenRef = ref<HTMLElement | null>(null)
const viewMode = ref<'table' | 'grid'>('table')

const filter = ref({
  keyword: '',
  ext: '',
})

const filtered = computed(() => {
  let list = files.value
  const kw = filter.value.keyword.trim().toLowerCase()
  if (kw) {
    list = list.filter(
      (r) => r.name.toLowerCase().includes(kw) || r.path.toLowerCase().includes(kw) || r.uploader.toLowerCase().includes(kw)
    )
  }
  if (filter.value.ext) list = list.filter((r) => r.ext.toLowerCase() === filter.value.ext.toLowerCase())
  return list
})

const page = ref(1)
const pageSize = ref(12)
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

watch([filtered, pageSize], () => {
  const max = Math.max(1, Math.ceil(filtered.value.length / pageSize.value) || 1)
  if (page.value > max) page.value = max
})

const extOptions = computed(() => {
  const s = new Set(files.value.map((f) => f.ext))
  return [...s]
})

const uploadVisible = ref(false)
const uploadName = ref('')
const uploadSize = ref(102400)
const uploadExt = ref('pdf')

function openUpload() {
  uploadName.value = `新文件_${Date.now()}.pdf`
  uploadSize.value = 102400
  uploadExt.value = 'pdf'
  uploadVisible.value = true
}

function confirmUpload() {
  if (!uploadName.value.trim()) {
    ElMessage.warning('请输入文件名')
    return
  }
  const ext = uploadName.value.includes('.') ? uploadName.value.split('.').pop() || uploadExt.value : uploadExt.value
  store.addMockFile({
    name: uploadName.value.trim(),
    size: uploadSize.value,
    ext,
    uploader: userStore.userInfo?.username || 'admin',
  })
  uploadVisible.value = false
  ElMessage.success('上传成功')
}

function onBatchDelete() {
  if (!selected.value.length) {
    ElMessage.warning('请选择文件')
    return
  }
  ElMessageBox.confirm(`确定删除选中的 ${selected.value.length} 个文件？`, '提示', { type: 'warning' })
    .then(() => {
      store.removeFiles(selected.value.map((r) => r.id))
      selected.value = []
      ElMessage.success('已删除')
    })
    .catch(() => {})
}

function rowDelete(row: FileCenterRow) {
  ElMessageBox.confirm(`确定删除「${row.name}」？`, '提示', { type: 'warning' })
    .then(() => {
      store.removeFiles([row.id])
      ElMessage.success('已删除')
    })
    .catch(() => {})
}

function copyLink(row: FileCenterRow) {
  const url = `${window.location.origin}${row.path}`
  navigator.clipboard.writeText(url).then(
    () => ElMessage.success('链接已复制'),
    () => ElMessage.error('复制失败')
  )
}

function downloadMock(row: FileCenterRow) {
  ElMessage.success(`已开始下载：${row.name}`)
}

function refresh() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    ElMessage.success('已刷新')
  }, 200)
}

async function toggleFullscreen() {
  const el = fullscreenRef.value
  if (!el) return
  try {
    if (!document.fullscreenElement) await el.requestFullscreen()
    else await document.exitFullscreen()
  } catch {
    ElMessage.info('当前环境不支持全屏')
  }
}
</script>

<template>
  <div ref="fullscreenRef" class="sys-page art-full-height">
    <el-card v-show="showFilter" shadow="never" class="search-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="关键词">
          <el-input v-model="filter.keyword" clearable placeholder="文件名 / 路径 / 上传人" style="width: 220px" />
        </el-form-item>
        <el-form-item label="扩展名">
          <el-select v-model="filter.ext" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="e in extOptions" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="page = 1">查询</el-button>
          <el-button @click="filter = { keyword: '', ext: '' }; page = 1">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="table-toolbar">
        <div class="left">
          <el-button type="primary" :icon="Upload" @click="openUpload">上传</el-button>
          <el-button type="danger" plain :icon="Delete" @click="onBatchDelete">删除</el-button>
        </div>
        <div class="right-tools">
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="table">列表</el-radio-button>
            <el-radio-button value="grid">网格</el-radio-button>
          </el-radio-group>
          <el-tooltip content="筛选" placement="top">
            <el-button :icon="Search" circle @click="showFilter = !showFilter" />
          </el-tooltip>
          <el-tooltip content="刷新" placement="top">
            <el-button :icon="Refresh" circle @click="refresh" />
          </el-tooltip>
          <el-dropdown trigger="click" @command="(c: 'large' | 'default' | 'small') => (tableSize = c)">
            <el-button :icon="Grid" circle />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="large">宽松</el-dropdown-item>
                <el-dropdown-item command="default">默认</el-dropdown-item>
                <el-dropdown-item command="small">紧凑</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tooltip content="全屏" placement="top">
            <el-button :icon="FullScreen" circle @click="toggleFullscreen" />
          </el-tooltip>
        </div>
      </div>

      <el-table
        v-if="viewMode === 'table'"
        v-loading="loading"
        :data="paged"
        row-key="id"
        border
        :size="tableSize"
        @selection-change="selected = $event"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="预览" width="72">
          <template #default="{ row }">
            <div class="thumb" :style="{ background: row.thumbColor }">
              <el-icon :size="22" color="#fff"><Document /></el-icon>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="文件名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="path" label="存储路径" min-width="220" show-overflow-tooltip />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ store.formatFileSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="ext" label="扩展名" width="88" />
        <el-table-column prop="uploader" label="上传人" width="100" />
        <el-table-column prop="createdAt" label="上传时间" width="178" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Download" @click="downloadMock(row)">下载</el-button>
            <el-button type="primary" link :icon="Link" @click="copyLink(row)">复制链接</el-button>
            <el-button type="danger" link :icon="Delete" @click="rowDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else v-loading="loading" class="grid-wrap">
        <el-empty v-if="!paged.length" description="暂无文件" />
        <div v-else class="grid">
          <el-card
            v-for="row in paged"
            :key="row.id"
            shadow="hover"
            class="grid-card"
            :body-style="{ padding: '12px' }"
          >
            <div class="grid-thumb" :style="{ background: row.thumbColor }">
              <el-icon :size="36" color="#fff"><Document /></el-icon>
            </div>
            <div class="grid-name" :title="row.name">{{ row.name }}</div>
            <div class="grid-meta">{{ store.formatFileSize(row.size) }} · {{ row.ext }}</div>
            <div class="grid-actions">
              <el-button size="small" text type="primary" @click="downloadMock(row)">下载</el-button>
              <el-button size="small" text @click="copyLink(row)">链接</el-button>
              <el-button size="small" text type="danger" @click="rowDelete(row)">删除</el-button>
            </div>
          </el-card>
        </div>
      </div>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filtered.length"
          :page-sizes="[8, 12, 24]"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <el-dialog v-model="uploadVisible" title="上传文件" width="440px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="文件名">
          <el-input v-model="uploadName" placeholder="含扩展名，如 说明.pdf" />
        </el-form-item>
        <el-form-item label="大小(字节)">
          <el-input-number v-model="uploadSize" :min="1" :max="999999999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="扩展名">
          <el-input v-model="uploadExt" placeholder="用于无后缀时" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUpload">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.sys-page.art-full-height {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100vh - 120px);
}
.search-card {
  border-radius: 12px;
  :deep(.el-card__body) {
    padding-bottom: 4px;
  }
}
.table-card {
  flex: 1;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
}
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
  .left {
    display: flex;
    gap: 8px;
  }
  .right-tools {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
}
.thumb {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.grid-wrap {
  min-height: 200px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.grid-card {
  border-radius: 12px;
}
.grid-thumb {
  height: 88px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}
.grid-name {
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.grid-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.grid-actions {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.sys-page:fullscreen {
  background: var(--el-bg-color);
  padding: 16px;
  overflow: auto;
}
</style>
