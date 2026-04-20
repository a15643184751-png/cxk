import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNoticeStore = defineStore('notice', () => {
  // 后勤：待审批采购申请
  const newPurchaseCount = ref(0)
  // 供应商：待接单
  const supplierOrderCount = ref(0)
  // 仓储：待入库
  const warehouseStockInCount = ref(0)
  // 仓储：待出库
  const warehouseStockOutCount = ref(0)
  // 后勤/仓储：待创建配送
  const deliveryToCreateCount = ref(0)
  // 教师：待签收
  const teacherReceiveCount = ref(0)

  function setNewPurchaseCount(count: number) {
    newPurchaseCount.value = Math.max(0, Number(count) || 0)
  }
  function clearNewPurchaseCount() {
    newPurchaseCount.value = 0
  }

  function setSupplierOrderCount(count: number) {
    supplierOrderCount.value = Math.max(0, Number(count) || 0)
  }
  function clearSupplierOrderCount() {
    supplierOrderCount.value = 0
  }

  function setWarehouseStockInCount(count: number) {
    warehouseStockInCount.value = Math.max(0, Number(count) || 0)
  }
  function setWarehouseStockOutCount(count: number) {
    warehouseStockOutCount.value = Math.max(0, Number(count) || 0)
  }
  function clearWarehouseCounts() {
    warehouseStockInCount.value = 0
    warehouseStockOutCount.value = 0
  }

  function setDeliveryToCreateCount(count: number) {
    deliveryToCreateCount.value = Math.max(0, Number(count) || 0)
  }
  function clearDeliveryToCreateCount() {
    deliveryToCreateCount.value = 0
  }

  function setTeacherReceiveCount(count: number) {
    teacherReceiveCount.value = Math.max(0, Number(count) || 0)
  }
  function clearTeacherReceiveCount() {
    teacherReceiveCount.value = 0
  }

  /** 根据 path 返回对应角标数量 */
  function getBadgeForPath(path: string): number {
    const p = path.startsWith('/') ? path : `/${path}`
    if (p === '/purchase') return newPurchaseCount.value
    if (p === '/supplier/orders') return supplierOrderCount.value
    if (p === '/stock/in') return warehouseStockInCount.value
    if (p === '/stock/out') return warehouseStockOutCount.value
    if (p === '/delivery') return deliveryToCreateCount.value
    if (p === '/my-applications' || p === '/teacher/personal') return teacherReceiveCount.value
    return 0
  }

  return {
    newPurchaseCount,
    setNewPurchaseCount,
    clearNewPurchaseCount,
    supplierOrderCount,
    setSupplierOrderCount,
    clearSupplierOrderCount,
    warehouseStockInCount,
    warehouseStockOutCount,
    setWarehouseStockInCount,
    setWarehouseStockOutCount,
    clearWarehouseCounts,
    deliveryToCreateCount,
    setDeliveryToCreateCount,
    clearDeliveryToCreateCount,
    teacherReceiveCount,
    setTeacherReceiveCount,
    clearTeacherReceiveCount,
    getBadgeForPath,
  }
})
