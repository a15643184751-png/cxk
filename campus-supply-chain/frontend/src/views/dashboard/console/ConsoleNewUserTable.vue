<script setup lang="ts">
import { ref, computed } from 'vue'

const radio = ref('本月')

const palette = ['#4f46e5', '#0d9488', '#ea580c', '#6366f1', '#22c55e', '#8b5cf6', '#0ea5e9', '#d946ef']

const seeds: [string, string, number][] = [
  ['北区中心仓', '仓储物流', 1],
  ['南区备货仓', '仓储物流', 1],
  ['后勤采购一组', '校本部', 1],
  ['供应商-康源', '合作企业', 0],
  ['供应商-晨光', '合作企业', 0],
  ['辅导员事务中心', '学工部门', 0],
  ['信息中心', '系统管理', 1],
  ['质检实验室', '教辅', 1],
  ['车队调度', '运输', 1],
  ['财务对账组', '行政', 0],
  ['安全运营', '网信', 1],
  ['教材服务中心', '教务协同', 0],
  ['防疫物资专班', '应急', 1],
  ['餐饮耗材对接', '后勤', 0],
  ['设备维修站', '资产', 1],
  ['校园超市供应链', '商业', 0],
  ['绿色回收项目', '环保', 1],
  ['国际学院物资', '院系', 0],
  ['研究生公寓配发', '宿管', 1],
  ['图书馆资产科', '教辅', 0],
]

const tableData = computed(() =>
  seeds.map((s, i) => ({
    username: s[0],
    province: s[1],
    sex: s[2],
    pro: 52 + ((i * 17) % 48),
    color: palette[i % palette.length],
  }))
)
</script>

<template>
  <div class="dcc-card dcc-table-card">
    <div class="hdr">
      <div>
        <h4>供应链协同履约</h4>
        <p class="sub">各业务单元本月闭环进度</p>
      </div>
      <el-radio-group v-model="radio" size="small">
        <el-radio-button value="本月">本月</el-radio-button>
        <el-radio-button value="上月">上月</el-radio-button>
        <el-radio-button value="今年">今年</el-radio-button>
      </el-radio-group>
    </div>
    <div class="table-wrap">
      <el-table :data="tableData" class="inner-table" size="default" :border="false" stripe>
        <el-table-column label="业务单元" min-width="168">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="36" class="av">{{ row.username.slice(0, 1) }}</el-avatar>
              <span>{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="province" label="归属条线" width="108" show-overflow-tooltip />
        <el-table-column label="模式" width="72" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.sex === 1 ? 'primary' : 'info'" effect="plain">
              {{ row.sex === 1 ? '执行' : '协同' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="闭环进度" min-width="200">
          <template #default="{ row }">
            <el-progress :percentage="row.pro" :color="row.color" :stroke-width="5" />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dcc-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 22px 22px 18px;
  margin-bottom: 20px;
  box-sizing: border-box;
  min-height: 400px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.hdr {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
  h4 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  .sub {
    margin: 8px 0 0;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
    max-width: 420px;
  }
}
.table-wrap {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #f0f0f0;
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  .av {
    background: rgba(79, 70, 229, 0.12);
    color: #4f46e5;
    font-weight: 600;
  }
}
.inner-table {
  width: 100%;
  --el-table-header-bg-color: #fafafa;
  --el-table-border-color: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8faff;
}
:deep(.el-table__inner-wrapper::before) {
  display: none;
}
:deep(.el-table__body td) {
  border-bottom: 1px solid #f5f5f5;
}
</style>
