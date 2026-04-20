<script setup lang="ts">
import { ref, reactive, computed, onMounted, watchEffect } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, User } from '@element-plus/icons-vue'
import { listUsers, createUser } from '@/api/user'
import type { UserItem, UserCreateParams } from '@/api/user'
import { ROLE_LABELS } from '@/types/role'
import type { RoleType } from '@/types/role'

const loading = ref(false)
const tableData = ref<UserItem[]>([])
const selectedRows = ref<UserItem[]>([])

const searchForm = reactive({
  keyword: '',
  role: '' as '' | RoleType,
})

const roleFilterOptions = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))

const filteredList = computed(() => {
  let list = tableData.value
  const kw = searchForm.keyword.trim().toLowerCase()
  if (kw) {
    list = list.filter(
      (u) =>
        u.username.toLowerCase().includes(kw) ||
        (u.real_name || '').toLowerCase().includes(kw) ||
        (u.phone || '').includes(kw)
    )
  }
  if (searchForm.role) {
    list = list.filter((u) => u.role === searchForm.role)
  }
  return list
})

const page = ref(1)
const pageSize = ref(20)
const pagedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredList.value.slice(start, start + pageSize.value)
})

watchEffect(() => {
  const maxPage = Math.max(1, Math.ceil(filteredList.value.length / pageSize.value) || 1)
  if (page.value > maxPage) page.value = maxPage
})

const dialogVisible = ref(false)
const submitLoading = ref(false)
const form = reactive<UserCreateParams & { passwordConfirm?: string }>({
  username: '',
  password: '',
  real_name: '',
  role: 'counselor_teacher',
  department: '',
  phone: '',
  passwordConfirm: '',
})

function resetForm() {
  form.username = ''
  form.password = ''
  form.real_name = ''
  form.role = 'counselor_teacher'
  form.department = ''
  form.phone = ''
  form.passwordConfirm = ''
}

async function fetchData() {
  loading.value = true
  try {
    const res: unknown = await listUsers()
    tableData.value = Array.isArray(res) ? res : (res as { data?: UserItem[] })?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
}

function onResetSearch() {
  searchForm.keyword = ''
  searchForm.role = ''
  page.value = 1
}

function openAdd() {
  resetForm()
  dialogVisible.value = true
}

async function handleCreate() {
  if (!form.username?.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!form.password || form.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (form.password !== form.passwordConfirm) {
    ElMessage.warning('两次密码不一致')
    return
  }
  submitLoading.value = true
  try {
    await createUser({
      username: form.username.trim(),
      password: form.password,
      real_name: form.real_name?.trim() || undefined,
      role: form.role,
      department: form.department?.trim() || undefined,
      phone: form.phone?.trim() || undefined,
    })
    ElMessage.success('添加成功')
    dialogVisible.value = false
    await fetchData()
  } catch {
    /* request 拦截器已提示 */
  } finally {
    submitLoading.value = false
  }
}

function roleLabel(role: string) {
  return ROLE_LABELS[role as RoleType] ?? role
}

function onDelete(row: UserItem) {
  ElMessageBox.confirm(`确定删除用户「${row.username}」吗？（当前版本后端未开放删除接口，此为界面预留）`, '提示', {
    type: 'warning',
  }).catch(() => {})
}

onMounted(fetchData)
</script>

<template>
  <div class="sys-page art-full-height">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" class="search-form" @submit.prevent="onSearch">
        <el-form-item label="关键词">
          <el-input
            v-model="searchForm.keyword"
            clearable
            placeholder="用户名 / 姓名 / 手机"
            style="width: 220px"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="searchForm.role" clearable placeholder="全部" style="width: 160px">
            <el-option v-for="o in roleFilterOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
          <el-button @click="onResetSearch">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="table-toolbar">
        <div class="left">
          <el-button type="primary" :icon="Plus" @click="openAdd">新增用户</el-button>
        </div>
        <el-button :icon="Refresh" circle @click="fetchData" />
      </div>

      <el-table
        v-loading="loading"
        :data="pagedData"
        row-key="id"
        border
        @selection-change="selectedRows = $event"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column label="用户" min-width="220">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="40" class="av">
                <el-icon><User /></el-icon>
              </el-avatar>
              <div>
                <div class="uname">{{ row.username }}</div>
                <div class="sub">{{ row.real_name }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机" width="130" />
        <el-table-column prop="department" label="部门" min-width="120" show-overflow-tooltip />
        <el-table-column label="角色" width="140">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ roleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filteredList.length"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新增用户" width="440px" destroy-on-close @closed="resetForm">
      <el-form :model="form" label-width="88px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input v-model="form.passwordConfirm" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="o in roleFilterOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.department" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="form.phone" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.art-full-height {
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
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  .av {
    flex-shrink: 0;
    background: var(--primary-muted);
    color: var(--primary);
  }
  .uname {
    font-weight: 500;
    color: var(--text-primary);
  }
  .sub {
    font-size: 12px;
    color: var(--text-muted);
  }
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
