<script setup lang="ts">
import { reactive, computed } from 'vue'

interface TodoItem {
  username: string
  date: string
  complate: boolean
}

const list = reactive<TodoItem[]>([
  { username: '核对本周采购到货与发票影像', date: '上午 09:00', complate: true },
  { username: '同步仓储安全库存与补货阈值', date: '上午 09:30', complate: true },
  { username: '回访重点供应商交付准时率', date: '上午 10:15', complate: true },
  { username: '整理溯源批次抽检与留样记录', date: '上午 11:00', complate: false },
  { username: '更新后勤 / 仓储双大屏指标口径', date: '下午 01:30', complate: false },
  { username: '复核 IDS 今日拦截事件闭环', date: '下午 02:20', complate: false },
  { username: '导出上月敏感操作审计抽样表', date: '下午 03:00', complate: false },
  { username: '联调供应商门户对账文件格式', date: '下午 04:10', complate: false },
  { username: '编写 Q1 供应链安全演练脚本', date: '下午 05:30', complate: false },
])

const pending = computed(() => list.filter((x) => !x.complate).length)
</script>

<template>
  <div class="dcc-card dcc-todo">
    <div class="hdr">
      <h4>待办事项</h4>
      <p class="sub">待处理 <span class="danger">{{ pending }}</span> · 管理员日常巡检</p>
    </div>
    <el-scrollbar class="scroll">
      <div v-for="(item, index) in list" :key="index" class="row">
        <div class="txt">
          <p class="t">{{ item.username }}</p>
          <p class="d">{{ item.date }}</p>
        </div>
        <el-checkbox v-model="item.complate" />
      </div>
    </el-scrollbar>
  </div>
</template>

<style scoped lang="scss">
.dcc-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 22px;
  margin-bottom: 20px;
  box-sizing: border-box;
  min-height: 360px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.hdr h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.sub {
  margin: 8px 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.45;
  .danger {
    color: var(--el-color-danger);
    font-weight: 600;
  }
}
.scroll {
  height: calc(100% - 56px);
  min-height: 260px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  min-height: 52px;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
  &:last-child {
    border-bottom: none;
  }
  .txt {
    min-width: 0;
    flex: 1;
  }
  .t {
    margin: 0;
    font-size: 13px;
    line-height: 1.4;
  }
  .d {
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>
