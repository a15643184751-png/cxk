<script setup lang="ts">
defineProps<{
  items: { username: string; type: string; target: string }[]
}>()
</script>

<template>
  <div class="dcc-card dcc-dynamic">
    <div class="hdr">
      <h4>全链路动态</h4>
      <p class="sub">采购、仓储、配送、供应商与安全侧摘要流</p>
    </div>
    <el-scrollbar class="scroll">
      <div
        v-for="(item, index) in items"
        :key="index"
        class="line"
      >
        <span class="u">{{ item.username }}</span>
        <span class="t">{{ item.type }}</span>
        <span class="tar">{{ item.target }}</span>
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
  margin: 6px 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.scroll {
  height: calc(100% - 52px);
  min-height: 260px;
}
.line {
  line-height: 1.45;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  &:last-child {
    border-bottom: none;
  }
  .u {
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  .t {
    color: var(--el-text-color-secondary);
  }
  .tar {
    flex: 1;
    min-width: 140px;
    color: #4f46e5;
  }
}
</style>
