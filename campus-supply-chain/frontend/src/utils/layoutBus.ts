import { useEventBus } from '@vueuse/core'

export const openSettingsBus = useEventBus<void>('campus-open-settings')
export const openSearchBus = useEventBus<void>('campus-open-search')
export const openChatBus = useEventBus<void>('campus-open-chat')
export const openLockBus = useEventBus<void>('campus-open-lock')
