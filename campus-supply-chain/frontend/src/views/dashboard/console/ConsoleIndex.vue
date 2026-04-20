<script setup lang="ts">
import type { Component } from 'vue'
import ConsoleCardList from './ConsoleCardList.vue'
import ConsoleUserOverview from './ConsoleUserOverview.vue'
import ConsolePurchaseLine from './ConsolePurchaseLine.vue'
import ConsoleVisitMock from './ConsoleVisitMock.vue'
import ConsoleNewUserTable from './ConsoleNewUserTable.vue'
import ConsoleDynamic from './ConsoleDynamic.vue'
import ConsoleTodoList from './ConsoleTodoList.vue'
import ConsoleShortcuts from './ConsoleShortcuts.vue'
import ConsoleExpiring from './ConsoleExpiring.vue'
import ConsoleAbout from './ConsoleAbout.vue'

withDefaults(
  defineProps<{
    statCards: { title: string; value: number; trend: string; trendValue: string; icon: string; path: string }[]
    chartData: { x: string[]; purchase: number[]; output: number[] }
    showPurchaseChart: boolean
    dynamicItems: { username: string; type: string; target: string }[]
    shortcuts: { icon: Component; label: string; path: string }[]
    expiringItems: { name: string; days: number; count: number }[]
    showExpiring: boolean
    /** 管理员端：略增强控制台视觉层次 */
    adminConsole?: boolean
  }>(),
  { adminConsole: false }
)
</script>

<template>
  <div class="console-root" :class="{ 'console-root--admin': adminConsole }">
    <ConsoleCardList v-if="statCards.length" :cards="statCards" />

    <el-row :gutter="20">
      <el-col :sm="24" :md="12" :lg="10">
        <ConsoleUserOverview />
      </el-col>
      <el-col :sm="24" :md="12" :lg="14">
        <ConsolePurchaseLine
          v-if="showPurchaseChart && chartData.x?.length"
          :show="true"
          :chart-data="chartData"
        />
        <ConsoleVisitMock v-else />
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :sm="24" :md="24" :lg="12">
        <ConsoleNewUserTable />
      </el-col>
      <el-col :sm="24" :md="12" :lg="6">
        <ConsoleDynamic :items="dynamicItems" />
      </el-col>
      <el-col :sm="24" :md="12" :lg="6">
        <ConsoleTodoList />
      </el-col>
    </el-row>

    <el-row v-if="shortcuts.length || (showExpiring && expiringItems.length)" :gutter="20">
      <el-col :xs="24" :md="showExpiring && expiringItems.length ? 16 : 24">
        <ConsoleShortcuts :items="shortcuts" />
      </el-col>
      <el-col v-if="showExpiring && expiringItems.length" :xs="24" :md="8">
        <ConsoleExpiring :items="expiringItems" />
      </el-col>
    </el-row>

    <ConsoleAbout />
  </div>
</template>

<style scoped lang="scss">
.console-root {
  display: flex;
  flex-direction: column;
}
.console-root--admin {
  padding-bottom: 8px;
}
</style>
