<!-- 拖拽验证（自 art-design-pro ArtDragVerify，图标改为 Element Plus） -->
<template>
  <div
    ref="dragVerify"
    class="drag_verify"
    :style="dragVerifyStyle"
    @mousemove="dragMoving"
    @mouseup="dragFinish"
    @mouseleave="dragFinish"
    @touchmove.prevent="dragMoving"
    @touchend="dragFinish"
  >
    <div ref="progressBar" class="dv_progress_bar" :class="{ goFirst2: isOk }" :style="progressBarStyle" />
    <div ref="messageRef" class="dv_text" :style="textStyle">{{ message }}</div>
    <div
      ref="handler"
      class="dv_handler dv_handler_bg"
      :class="{ goFirst: isOk }"
      :style="handlerStyle"
      @mousedown="dragStart"
      @touchstart="dragStart"
    >
      <el-icon v-if="value" :size="18"><CircleCheck /></el-icon>
      <el-icon v-else :size="18"><DArrowRight /></el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  reactive,
  toRefs,
  computed,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from 'vue'
import { CircleCheck, DArrowRight } from '@element-plus/icons-vue'

defineOptions({ name: 'DragVerify' })

const emit = defineEmits<{
  'update:value': [v: boolean]
  handlerMove: []
  passCallback: []
}>()

const props = withDefaults(
  defineProps<{
    value: boolean
    width?: number | string
    height?: number
    text?: string
    successText?: string
    background?: string
    progressBarBg?: string
    completedBg?: string
    circle?: boolean
    radius?: string
    handlerBg?: string
    textSize?: string
    textColor?: string
  }>(),
  {
    value: false,
    width: '100%',
    height: 40,
    text: '按住滑块拖动',
    successText: '验证通过',
    background: '#eee',
    progressBarBg: '#5d5fe3',
    completedBg: '#57D187',
    circle: false,
    radius: '8px',
    handlerBg: '#fff',
    textSize: '13px',
    textColor: '#333',
  }
)

const state = reactive({
  isMoving: false,
  x: 0,
  isOk: false,
})
const { isOk } = toRefs(state)

const dragVerify = ref<HTMLElement>()
const messageRef = ref<HTMLElement>()
const handler = ref<HTMLElement>()
const progressBar = ref<HTMLElement>()

let startX = 0,
  startY = 0,
  moveX = 0,
  moveY = 0
const onTouchStart = (e: TouchEvent) => {
  startX = e.targetTouches[0].pageX
  startY = e.targetTouches[0].pageY
}
const onTouchMove = (e: TouchEvent) => {
  moveX = e.targetTouches[0].pageX
  moveY = e.targetTouches[0].pageY
  if (Math.abs(moveX - startX) > Math.abs(moveY - startY)) e.preventDefault()
}

onMounted(() => {
  document.addEventListener('touchstart', onTouchStart)
  document.addEventListener('touchmove', onTouchMove, { passive: false })
  dragVerify.value?.style.setProperty('--textColor', props.textColor)
  nextTick(() => {
    const w = getNumericWidth()
    dragVerify.value?.style.setProperty('--width', Math.floor(w / 2) + 'px')
    dragVerify.value?.style.setProperty('--pwidth', -Math.floor(w / 2) + 'px')
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('touchstart', onTouchStart)
  document.removeEventListener('touchmove', onTouchMove)
})

function getNumericWidth(): number {
  if (typeof props.width === 'string') return dragVerify.value?.offsetWidth || 260
  return props.width
}

function getStyleWidth(): string {
  if (typeof props.width === 'string') return props.width
  return props.width + 'px'
}

const handlerStyle = {
  left: '0',
  width: props.height + 'px',
  height: props.height + 'px',
  background: props.handlerBg,
}

const dragVerifyStyle = computed(() => ({
  width: getStyleWidth(),
  height: props.height + 'px',
  lineHeight: props.height + 'px',
  background: props.background,
  borderRadius: props.circle ? props.height / 2 + 'px' : props.radius,
}))

const progressBarStyle = {
  background: props.progressBarBg,
  height: props.height + 'px',
  borderRadius: props.circle
    ? props.height / 2 + 'px 0 0 ' + props.height / 2 + 'px'
    : props.radius,
}

const textStyle = computed(() => ({ fontSize: props.textSize }))

const message = computed(() => (props.value ? props.successText : props.text))

function dragStart(e: MouseEvent | TouchEvent) {
  if (!props.value && handler.value) {
    state.isMoving = true
    handler.value.style.transition = 'none'
    const pageX = 'touches' in e ? e.touches[0].pageX : e.pageX
    state.x = pageX - parseInt(handler.value.style.left.replace('px', ''), 10)
    emit('handlerMove')
  }
}

function dragMoving(e: MouseEvent | TouchEvent) {
  if (!state.isMoving || props.value || !handler.value || !progressBar.value) return
  const pageX = 'touches' in e ? e.touches[0].pageX : e.pageX
  const numericWidth = getNumericWidth()
  let _x = pageX - state.x
  if (_x > 0 && _x <= numericWidth - props.height) {
    handler.value.style.left = _x + 'px'
    progressBar.value.style.width = _x + props.height / 2 + 'px'
  } else if (_x > numericWidth - props.height) {
    handler.value.style.left = numericWidth - props.height + 'px'
    progressBar.value.style.width = numericWidth - props.height / 2 + 'px'
    passVerify()
  }
}

function dragFinish(e: MouseEvent | TouchEvent) {
  if (!state.isMoving || props.value || !handler.value || !progressBar.value) return
  const numericWidth = getNumericWidth()
  const pageX =
    'changedTouches' in e && e.changedTouches?.length
      ? e.changedTouches[0].pageX
      : (e as MouseEvent).pageX
  let _x = pageX - state.x
  if (_x < numericWidth - props.height) {
    state.isOk = true
    handler.value.style.left = '0'
    handler.value.style.transition = 'all 0.2s'
    progressBar.value.style.width = '0'
    state.isOk = false
  } else {
    handler.value.style.transition = 'none'
    handler.value.style.left = numericWidth - props.height + 'px'
    progressBar.value.style.width = numericWidth - props.height / 2 + 'px'
    passVerify()
  }
  state.isMoving = false
}

function passVerify() {
  emit('update:value', true)
  state.isMoving = false
  if (!progressBar.value || !messageRef.value) return
  progressBar.value.style.background = props.completedBg
  messageRef.value.style.webkitTextFillColor = 'unset'
  messageRef.value.style.animation = 'slidetounlock2 2s cubic-bezier(0, 0.2, 1, 1) infinite'
  messageRef.value.style.color = '#fff'
  emit('passCallback')
}

function reset() {
  if (!handler.value || !progressBar.value || !messageRef.value) return
  handler.value.style.left = '0'
  progressBar.value.style.width = '0'
  progressBar.value.style.background = props.progressBarBg
  messageRef.value.style.webkitTextFillColor = 'transparent'
  messageRef.value.style.animation = 'slidetounlock 2s cubic-bezier(0, 0.2, 1, 1) infinite'
  messageRef.value.style.color = props.background
  emit('update:value', false)
  state.isOk = false
  state.isMoving = false
  state.x = 0
}

defineExpose({ reset })
</script>

<style lang="scss" scoped>
.drag_verify {
  position: relative;
  box-sizing: border-box;
  overflow: hidden;
  text-align: center;
  border: 1px solid var(--el-border-color);

  .dv_handler {
    position: absolute;
    top: 0;
    left: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: grab;
    color: var(--el-text-color-secondary);
    z-index: 2;
    &:active {
      cursor: grabbing;
    }
  }

  .dv_progress_bar {
    position: absolute;
    left: 0;
    top: 0;
    width: 0;
    z-index: 0;
  }

  .dv_text {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: transparent;
    user-select: none;
    z-index: 1;
    background: linear-gradient(
      to right,
      var(--textColor) 0%,
      var(--textColor) 40%,
      #fff 50%,
      var(--textColor) 60%,
      var(--textColor) 100%
    );
    -webkit-background-clip: text;
    background-clip: text;
    animation: slidetounlock 2s cubic-bezier(0, 0.2, 1, 1) infinite;
    -webkit-text-fill-color: transparent;
  }
}

.goFirst {
  left: 0 !important;
  transition: left 0.5s;
}

.goFirst2 {
  width: 0 !important;
  transition: width 0.5s;
}
</style>

<style lang="scss">
@keyframes slidetounlock {
  0% {
    background-position: var(--pwidth) 0;
  }
  100% {
    background-position: var(--width) 0;
  }
}
@keyframes slidetounlock2 {
  0%,
  100% {
    background-position: var(--pwidth) 0;
  }
}
</style>
