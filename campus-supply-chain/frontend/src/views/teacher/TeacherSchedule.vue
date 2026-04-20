<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { pushPromptToWorkbench } from '@/utils/teacherWorkbenchBus'

const CAL_KEY = 'teacher-personal-calendar-v1'
const TODO_KEY = 'teacher-daily-todo-v1'

type CalType = 'course' | 'activity' | 'event' | 'other'

interface PersonalEvent {
  id: string
  date: string
  title: string
  type: CalType
  typeOther?: string
  start: string
  end: string
}

interface TodoRow {
  id: string
  title: string
  done: boolean
  day: string
}

const router = useRouter()
const mainTab = ref<'calendar' | 'todo'>('calendar')

const calendarDate = ref(new Date())
const personalEvents = ref<PersonalEvent[]>([])
const globalEvents = ref<{ date: string; title: string }[]>([])

const dlgVisible = ref(false)
const form = ref({
  title: '',
  type: 'course' as CalType,
  typeOther: '',
  start: '09:00',
  end: '10:40',
  date: '',
})

const newTodoTitle = ref('')
const todos = ref<TodoRow[]>([])

function pad(n: number) {
  return n < 10 ? `0${n}` : `${n}`
}

function seedGlobal() {
  const y = calendarDate.value.getFullYear()
  const m = calendarDate.value.getMonth() + 1
  const ym = `${y}-${pad(m)}`
  const base = [
    { date: `${ym}-12`, title: '校级教学常规检查周' },
    { date: `${ym}-18`, title: '大型学科竞赛日' },
    { date: `${ym}-25`, title: '教职工趣味运动会' },
  ]
  if (m === 4) {
    globalEvents.value = [
      ...base,
      { date: `${ym}-04`, title: '清明节放假调休' },
      { date: `${ym}-07`, title: '本科教学质量月动员' },
      { date: `${ym}-15`, title: '春季校园招聘双选会（理工类专场）' },
      { date: `${ym}-20`, title: '期中考试周（全校统一安排）' },
      { date: `${ym}-28`, title: '五一假期前安全稳定工作部署' },
    ]
  } else {
    globalEvents.value = base
  }
}

/** 首次进入且无本地日程时，写入信息学院教师典型 4 月安排（含 4.23 期中考试） */
const PERSONAL_SEED_VERSION = '3'
const PERSONAL_SEED_FLAG = `${CAL_KEY}-seeded-v${PERSONAL_SEED_VERSION}`

function defaultPersonalApril2026(): PersonalEvent[] {
  const raw: Array<{
    date: string
    title: string
    type: CalType
    start: string
    end: string
    typeOther?: string
  }> = [
    { date: '2026-04-01', title: '全院教职工政治理论学习', type: 'activity', start: '14:00', end: '15:30' },
    { date: '2026-04-02', title: '《Python程序设计》· 信息楼402', type: 'course', start: '10:00', end: '11:40' },
    { date: '2026-04-03', title: '研究生组会 · 课题进度汇报', type: 'activity', start: '19:00', end: '21:00' },
    { date: '2026-04-07', title: '教研室集体备课 · 算法与数据结构', type: 'activity', start: '14:00', end: '16:00' },
    { date: '2026-04-08', title: '《数据结构》实验课 · 机房B301', type: 'course', start: '14:00', end: '16:30' },
    { date: '2026-04-09', title: '课程思政案例材料校内提交', type: 'event', start: '17:00', end: '17:00' },
    { date: '2026-04-10', title: '信息学院学风建设座谈会', type: 'activity', start: '15:00', end: '16:30' },
    { date: '2026-04-11', title: '《数据库系统》上机 · 机房B302', type: 'course', start: '08:00', end: '09:40' },
    { date: '2026-04-14', title: '国自然形式审查材料系统提交', type: 'event', start: '09:00', end: '12:00' },
    { date: '2026-04-15', title: '《Web前端开发》· 信息楼401', type: 'course', start: '10:00', end: '11:40' },
    { date: '2026-04-15', title: '院务会（列席）', type: 'activity', start: '14:30', end: '16:00' },
    { date: '2026-04-16', title: '本科生毕业论文中期检查答辩', type: 'event', start: '08:30', end: '12:00' },
    { date: '2026-04-17', title: '监考培训与考纪研读', type: 'activity', start: '15:00', end: '16:30' },
    { date: '2026-04-21', title: '期中复习答疑周 · 办公室答疑', type: 'course', start: '14:00', end: '17:00' },
    { date: '2026-04-22', title: 'Python课程大作业收取截止', type: 'event', start: '23:59', end: '23:59' },
    { date: '2026-04-23', title: '期中考试 · 概率论与数理统计（信息楼阶梯教室）', type: 'event', start: '08:00', end: '10:00' },
    { date: '2026-04-24', title: '阅卷与成绩系统录入', type: 'activity', start: '09:00', end: '17:00' },
    { date: '2026-04-26', title: '实验室设备例行巡检（签字）', type: 'other', start: '10:00', end: '11:30', typeOther: '实验室安全' },
    { date: '2026-04-28', title: '学术报告：大模型与智能系统 · 报告厅', type: 'activity', start: '15:30', end: '17:00' },
    { date: '2026-04-29', title: '《计算机网络》· 信息楼403', type: 'course', start: '08:00', end: '09:40' },
    { date: '2026-04-30', title: '五一前实验室安全检查与门窗封条', type: 'event', start: '16:00', end: '17:30' },
  ]
  return raw.map((r, i) => ({
    id: `seed-pe-${i}`,
    date: r.date,
    title: r.title,
    type: r.type,
    start: r.start,
    end: r.end,
    typeOther: r.type === 'other' ? r.typeOther : undefined,
  }))
}

function seedPersonalDefaultsOnce() {
  if (typeof localStorage === 'undefined') return
  if (localStorage.getItem(PERSONAL_SEED_FLAG)) return
  if (personalEvents.value.length > 0) return
  personalEvents.value = defaultPersonalApril2026()
  savePersonal()
  localStorage.setItem(PERSONAL_SEED_FLAG, '1')
}

function loadPersonal() {
  try {
    const raw = localStorage.getItem(CAL_KEY)
    personalEvents.value = raw ? JSON.parse(raw) : []
  } catch {
    personalEvents.value = []
  }
}

function savePersonal() {
  localStorage.setItem(CAL_KEY, JSON.stringify(personalEvents.value))
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function loadTodos() {
  try {
    const raw = localStorage.getItem(TODO_KEY)
    todos.value = raw ? JSON.parse(raw) : []
  } catch {
    todos.value = []
  }
}

function saveTodos() {
  localStorage.setItem(TODO_KEY, JSON.stringify(todos.value))
}

onMounted(() => {
  loadPersonal()
  seedPersonalDefaultsOnce()
  loadTodos()
  seedGlobal()
})

watch(calendarDate, seedGlobal)

function openAddForDayStr(dayStr: string) {
  form.value = {
    title: '',
    type: 'course',
    typeOther: '',
    start: '09:00',
    end: '10:40',
    date: dayStr,
  }
  dlgVisible.value = true
}

function saveEvent() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写日程名称')
    return
  }
  personalEvents.value.push({
    id: `pe-${Date.now()}`,
    date: form.value.date,
    title: form.value.title.trim(),
    type: form.value.type,
    typeOther: form.value.type === 'other' ? form.value.typeOther.trim() : undefined,
    start: form.value.start,
    end: form.value.end,
  })
  savePersonal()
  dlgVisible.value = false
  ElMessage.success('已保存到本机浏览器，不会上传服务器')
}

function eventsOnDate(dayStr: string) {
  return personalEvents.value.filter((e) => e.date === dayStr)
}

function globalsOnDate(dayStr: string) {
  return globalEvents.value.filter((e) => e.date === dayStr)
}

const sidebarPrompts = computed(() => {
  const set = new Set<string>()
  const text = personalEvents.value.map((e) => `${e.title}${e.typeOther || ''}`).join(' ')
  if (/化学/.test(text)) set.add('申请化学课基础实验包')
  if (/体育|运动会|篮球|足球/.test(text)) set.add('申请运动会后勤保障常用物资包')
  if (/班会|年级|家长/.test(text)) set.add('申请班会与活动场地常用耗材')
  if (/实验|实验室|机房/.test(text)) set.add('申请通用实验耗材补充包')
  if (/期中|考试|阅卷|答辩/.test(text)) set.add('申请考务与阅卷常用物资（笔、密封条、草稿纸等）')
  if (set.size === 0 && text) set.add('根据我的日程，生成本周教学物资申领草稿')
  return [...set]
})

function goWorkbench(text: string) {
  pushPromptToWorkbench(text)
  void router.push('/teacher/workbench')
}

const todayTodos = computed(() => todos.value.filter((t) => t.day === todayStr()))

function addTodo() {
  const t = newTodoTitle.value.trim()
  if (!t) return
  todos.value.push({ id: `td-${Date.now()}`, title: t, done: false, day: todayStr() })
  newTodoTitle.value = ''
  saveTodos()
}

function toggleTodo(row: TodoRow) {
  row.done = !row.done
  saveTodos()
}

const todoPrompts = computed(() => {
  const set = new Set<string>()
  const text = todayTodos.value.map((t) => t.title).join(' ')
  if (/打印|复印|纸/.test(text)) set.add('申请 A4 打印纸与硒鼓耗材')
  if (/试卷|阅卷/.test(text)) set.add('申请阅卷笔、装订与密封条')
  if (/实验|药品/.test(text)) set.add('申请实验课耗材与安全用具')
  if (/清洁|消毒/.test(text)) set.add('申请消毒与地面清洁物资')
  if (set.size === 0 && text) set.add('根据今日待办，生成一条综合申领提示草稿')
  return [...set]
})

const typeLabels: Record<CalType, string> = {
  course: '课程',
  activity: '活动',
  event: '事件',
  other: '其他',
}
</script>

<template>
  <div class="schedule-page">
    <div class="page-intro">
      <h2>日程与规划</h2>
      <p>校历与个人安排分轨展示；AI 仅生成本地提示词并带入智能工作台，由您主动发送，保障隐私。</p>
    </div>

    <div class="sched-layout">
      <div class="sched-main">
        <el-tabs v-model="mainTab" class="sched-tabs">
          <el-tab-pane label="全景大日历" name="calendar">
            <div class="calendar-wrap">
              <el-calendar v-model="calendarDate">
                <template #date-cell="{ data }">
                  <div
                    class="cal-cell"
                    role="button"
                    tabindex="0"
                    @click="openAddForDayStr(data.day)"
                    @keydown.enter.prevent="openAddForDayStr(data.day)"
                  >
                    <span class="cal-day">{{ Number(data.day.split('-')[2]) }}</span>
                    <div v-for="g in globalsOnDate(data.day)" :key="'g-' + g.title + g.date" class="chip chip--global">
                      {{ g.title }}
                    </div>
                    <div
                      v-for="e in eventsOnDate(data.day)"
                      :key="e.id"
                      class="chip chip--personal"
                      @click.stop
                    >
                      {{ e.title }}
                    </div>
                  </div>
                </template>
              </el-calendar>
              <p class="cal-legend">
                <span class="lg g">灰底条为管理员下发校历（只读参考）</span>
                <span class="lg p">彩色条为您的个人规划；点击日期格可新增。</span>
              </p>
            </div>
          </el-tab-pane>

          <el-tab-pane label="今日待办" name="todo">
            <div class="todo-panel">
              <p class="todo-date">今日 {{ todayStr() }}</p>
              <div class="todo-add">
                <el-input
                  v-model="newTodoTitle"
                  placeholder="如：打印教案、整理试卷…"
                  clearable
                  @keydown.enter.prevent="addTodo"
                />
                <el-button type="primary" @click="addTodo">添加</el-button>
              </div>
              <ul class="todo-list">
                <li v-for="t in todayTodos" :key="t.id" :class="{ done: t.done }">
                  <el-checkbox
                    :model-value="t.done"
                    @update:model-value="(v: boolean) => { t.done = v; saveTodos(); }"
                  />
                  <span class="todo-title" @click="toggleTodo(t)">{{ t.title }}</span>
                </li>
                <li v-if="!todayTodos.length" class="todo-empty">暂无待办，添加后支持打勾划线。</li>
              </ul>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <aside class="sched-side">
        <template v-if="mainTab === 'calendar'">
          <h3 class="side-title">AI 建议提示词</h3>
          <p class="side-hint">
            仅读取本页「个人规划」内容，在本地生成文案；点击后写入智能工作台输入框，不会自动与后端交互。
          </p>
          <div class="capsules">
            <el-button
              v-for="p in sidebarPrompts"
              :key="p"
              class="cap"
              round
              @click="goWorkbench(p)"
            >
              {{ p }}
            </el-button>
            <p v-if="!sidebarPrompts.length" class="side-empty">添加个人日程后，这里会出现提示词胶囊。</p>
          </div>
        </template>
        <template v-else>
          <h3 class="side-title">待办物资建议</h3>
          <p class="side-hint">根据今日待办关键字生成本地提示词，同样仅带入工作台由您确认后发送。</p>
          <div class="capsules">
            <el-button v-for="p in todoPrompts" :key="p" class="cap" round @click="goWorkbench(p)">
              {{ p }}
            </el-button>
          </div>
        </template>
      </aside>
    </div>

    <el-dialog v-model="dlgVisible" title="新建个人规划" width="480px" destroy-on-close>
      <el-form label-width="96px">
        <el-form-item label="日期">
          <el-input :model-value="form.date" disabled />
        </el-form-item>
        <el-form-item label="日程名称" required>
          <el-input v-model="form.title" placeholder="如：高二化学实验课" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option v-for="(lab, k) in typeLabels" :key="k" :label="lab" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.type === 'other'" label="说明">
          <el-input v-model="form.typeOther" placeholder="手填类型说明" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-time-select v-model="form.start" start="07:00" step="00:10" end="22:00" placeholder="开始" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-select v-model="form.end" start="07:00" step="00:10" end="23:00" placeholder="结束" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlgVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEvent">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.schedule-page {
  padding: 0;
}
.page-intro {
  margin-bottom: 20px;
  h2 {
    margin: 0 0 8px 0;
    font-size: 20px;
    font-weight: 600;
  }
  p {
    margin: 0;
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
    max-width: 720px;
  }
}

.sched-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.sched-main {
  flex: 1;
  min-width: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 12px 16px 20px;
  box-shadow: var(--shadow-card);
}
.sched-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 12px;
  }
}

.calendar-wrap {
  :deep(.el-calendar-table .el-calendar-day) {
    height: 148px;
    vertical-align: top;
    padding: 2px;
  }
  :deep(.el-calendar__header) {
    padding-bottom: 12px;
  }
}

.cal-cell {
  height: 100%;
  min-height: 132px;
  border-radius: 8px;
  padding: 4px 3px 6px;
  cursor: pointer;
  transition: background 0.15s ease;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 2px;
  &:hover {
    background: var(--primary-muted);
  }
}
.cal-day {
  display: block;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 2px;
  flex-shrink: 0;
}
.chip {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  padding: 5px 7px;
  border-radius: 6px;
  margin-bottom: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  white-space: normal;
  word-break: break-word;
  letter-spacing: 0.01em;
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.06);
}
.chip--global {
  background: linear-gradient(180deg, #eef2f7 0%, #e2e8f0 100%);
  color: #1e293b;
  border: 1px solid #cbd5e1;
}
.chip--personal {
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.2) 0%, rgba(79, 70, 229, 0.14) 100%);
  color: #312e81;
  border: 1px solid rgba(67, 56, 202, 0.35);
}
.cal-legend {
  margin: 12px 0 0 0;
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  .lg.g::before {
    content: '';
    display: inline-block;
    width: 10px;
    height: 10px;
    background: #e5e7eb;
    margin-right: 6px;
    border-radius: 2px;
  }
  .lg.p::before {
    content: '';
    display: inline-block;
    width: 10px;
    height: 10px;
    background: rgba(79, 70, 229, 0.25);
    margin-right: 6px;
    border-radius: 2px;
  }
}

.todo-panel {
  padding: 8px 4px 12px;
}
.todo-date {
  font-weight: 600;
  margin: 0 0 12px 0;
}
.todo-add {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  max-width: 520px;
}
.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-width: 560px;
}
.todo-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-subtle);
  margin-bottom: 8px;
  background: var(--bg-elevated);
  &.done .todo-title {
    text-decoration: line-through;
    color: var(--text-muted);
  }
}
.todo-title {
  cursor: pointer;
  flex: 1;
  font-size: 14px;
}
.todo-empty {
  color: var(--text-muted);
  font-size: 13px;
  border: none !important;
  background: transparent !important;
}

.sched-side {
  width: 280px;
  flex-shrink: 0;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: linear-gradient(180deg, rgba(79, 70, 229, 0.06) 0%, var(--bg-card) 40%);
  position: sticky;
  top: 16px;
}
.side-title {
  margin: 0 0 10px 0;
  font-size: 15px;
  font-weight: 600;
}
.side-hint {
  margin: 0 0 14px 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.55;
}
.capsules {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cap {
  justify-content: center;
  white-space: normal;
  height: auto;
  min-height: 36px;
  padding: 8px 14px;
  line-height: 1.35;
}
.side-empty {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

@media (max-width: 960px) {
  .sched-layout {
    flex-direction: column;
  }
  .sched-side {
    width: 100%;
    position: static;
  }
}
</style>
