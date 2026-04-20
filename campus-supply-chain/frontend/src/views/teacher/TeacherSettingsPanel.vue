<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { ROLE_LABELS } from '@/types/role'
import type { RoleType } from '@/types/role'

const PREFS_KEY = 'teacher-workbench-prefs-v1'

const userStore = useUserStore()

const pwdForm = reactive({
  current: '',
  next: '',
  confirm: '',
})

const prefs = reactive({
  cardReorder: true,
  cardFavorites: true,
  cardShortcuts: true,
})

onMounted(() => {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    if (raw) {
      const j = JSON.parse(raw) as Partial<typeof prefs>
      if (typeof j.cardReorder === 'boolean') prefs.cardReorder = j.cardReorder
      if (typeof j.cardFavorites === 'boolean') prefs.cardFavorites = j.cardFavorites
      if (typeof j.cardShortcuts === 'boolean') prefs.cardShortcuts = j.cardShortcuts
    }
  } catch {
    /* ignore */
  }
})

function savePrefs() {
  localStorage.setItem(PREFS_KEY, JSON.stringify({ ...prefs }))
  ElMessage.success('偏好已保存（当前智能工作台为 AI 原生布局，下列项预留给后续版本接入）')
}

function savePassword() {
  if (!pwdForm.next || pwdForm.next !== pwdForm.confirm) {
    ElMessage.warning('两次新密码不一致')
    return
  }
  ElMessage.success('密码格式已校验通过')
  pwdForm.current = ''
  pwdForm.next = ''
  pwdForm.confirm = ''
}

const roleLabel = ROLE_LABELS[(userStore.userInfo?.role as RoleType) || 'counselor_teacher']
</script>

<template>
  <div class="settings-panel">
    <el-card shadow="never" class="block">
      <template #header><span class="card-title">账号信息</span></template>
      <el-descriptions :column="1" border size="default">
        <el-descriptions-item label="用户名">{{ userStore.userInfo?.username || '—' }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ userStore.userInfo?.real_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ roleLabel }}</el-descriptions-item>
        <el-descriptions-item label="部门">{{ userStore.userInfo?.department || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header><span class="card-title">修改密码</span></template>
      <el-form label-width="100px" style="max-width: 420px">
        <el-form-item label="当前密码">
          <el-input v-model="pwdForm.current" type="password" show-password placeholder="当前密码" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.next" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="savePassword">保存密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header><span class="card-title">个人偏好 · 工作台（预留）</span></template>
      <p class="hint">
        新版工作台以悬浮式输入、提示词胶囊与瀑布流为主；此处选项保存在本机，可与「胶囊/发现流」联动扩展。
      </p>
      <el-space direction="vertical" alignment="start" :size="12">
        <el-checkbox v-model="prefs.cardReorder">预留：快捷意图胶囊</el-checkbox>
        <el-checkbox v-model="prefs.cardFavorites">预留：发现流推荐</el-checkbox>
        <el-checkbox v-model="prefs.cardShortcuts">预留：极简模式</el-checkbox>
        <el-button type="primary" @click="savePrefs">保存偏好</el-button>
      </el-space>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.block {
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
}
.card-title {
  font-weight: 600;
}
.hint {
  margin: 0 0 16px 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
</style>
