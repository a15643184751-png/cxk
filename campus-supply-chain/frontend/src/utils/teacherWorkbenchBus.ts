import { ref } from 'vue'

/** 日程/待办等页写入；智能工作台内 AI 输入框在适当时机消费（本机桥接，不调用后端） */
export const workbenchChatPrefill = ref('')

export function pushPromptToWorkbench(text: string) {
  workbenchChatPrefill.value = String(text || '').trim()
}
