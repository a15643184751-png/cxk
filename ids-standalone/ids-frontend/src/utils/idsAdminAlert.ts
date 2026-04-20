import idsAlertWarningUrl from '@/assets/audio/ids-alert-warning.mp3?url'

export const IDS_ALERT_FOCUS_EVENT = 'ids-focus-event-request'
export const IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT = 'ids-alert-sound-settings-updated'

export type IDSFocusEventDetail = {
  eventId: number
  report?: boolean
}

export type IDSAlertSoundSettings = {
  enabled: boolean
  volume: number
  custom_audio_name: string
  custom_audio_updated_at: string | null
}

export type IDSAlertSoundAssetInfo = {
  name: string
  type: string
  size: number
  updatedAt: string
}

let activeAlertLoopAudio: HTMLAudioElement | null = null
let idsAlertAudioPrimed = false
let idsAlertAudioPrimingBound = false
let idsAlertAudioPrimingInFlight = false
let idsAlertPlaybackRetryBound = false
let idsAlertLoopRetryPending = false
const FIXED_ALERT_SOUND_SETTINGS: IDSAlertSoundSettings = {
  enabled: true,
  volume: 0.92,
  custom_audio_name: 'ids-alert-warning.mp3',
  custom_audio_updated_at: null,
}
const FIXED_ALERT_SOUND_INFO: IDSAlertSoundAssetInfo = {
  name: 'ids-alert-warning.mp3',
  type: 'audio/mpeg',
  size: 96698,
  updatedAt: '',
}

function clampVolume(value: unknown) {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) return 0.92
  return Math.min(1, Math.max(0, normalized))
}

function createAlertAudio(volume = 1) {
  const audio = new Audio(idsAlertWarningUrl)
  audio.preload = 'auto'
  audio.volume = clampVolume(volume)
  return audio
}

async function retryPendingIdsAlertLoopPlayback() {
  if (!idsAlertLoopRetryPending || !activeAlertLoopAudio) return false
  try {
    await activeAlertLoopAudio.play()
    idsAlertAudioPrimed = true
    idsAlertLoopRetryPending = false
    unbindIdsAlertPlaybackRetry()
    return true
  } catch {
    return false
  }
}

async function primeIdsAlertSoundFromGesture() {
  if (idsAlertAudioPrimed || idsAlertAudioPrimingInFlight || typeof window === 'undefined') return
  idsAlertAudioPrimingInFlight = true
  const audio = createAlertAudio(0.01)
  audio.muted = true
  try {
    await audio.play()
    audio.pause()
    audio.currentTime = 0
    idsAlertAudioPrimed = true
    unbindGlobalIdsAlertAudioPriming()
    await retryPendingIdsAlertLoopPlayback()
  } catch {
    idsAlertAudioPrimed = false
  } finally {
    idsAlertAudioPrimingInFlight = false
  }
}

function handleIdsAlertAudioPrimingGesture() {
  void primeIdsAlertSoundFromGesture()
}

function handleIdsAlertPlaybackRetryGesture() {
  void primeIdsAlertSoundFromGesture().finally(() => {
    void retryPendingIdsAlertLoopPlayback()
  })
}

function handleIdsAlertPlaybackRetryVisibilityChange() {
  if (typeof document !== 'undefined' && document.hidden) return
  void retryPendingIdsAlertLoopPlayback()
}

function bindIdsAlertPlaybackRetry() {
  if (typeof window === 'undefined' || idsAlertPlaybackRetryBound) return
  idsAlertPlaybackRetryBound = true
  window.addEventListener('pointerdown', handleIdsAlertPlaybackRetryGesture, {
    capture: true,
    passive: true,
  })
  window.addEventListener('keydown', handleIdsAlertPlaybackRetryGesture, { capture: true })
  window.addEventListener('touchstart', handleIdsAlertPlaybackRetryGesture, {
    capture: true,
    passive: true,
  })
  window.addEventListener('focus', handleIdsAlertPlaybackRetryVisibilityChange)
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleIdsAlertPlaybackRetryVisibilityChange)
  }
}

function unbindIdsAlertPlaybackRetry() {
  if (typeof window === 'undefined' || !idsAlertPlaybackRetryBound) return
  idsAlertPlaybackRetryBound = false
  window.removeEventListener('pointerdown', handleIdsAlertPlaybackRetryGesture, true)
  window.removeEventListener('keydown', handleIdsAlertPlaybackRetryGesture, true)
  window.removeEventListener('touchstart', handleIdsAlertPlaybackRetryGesture, true)
  window.removeEventListener('focus', handleIdsAlertPlaybackRetryVisibilityChange)
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleIdsAlertPlaybackRetryVisibilityChange)
  }
}

export function bindGlobalIdsAlertAudioPriming() {
  if (typeof window === 'undefined' || idsAlertAudioPrimingBound) return
  idsAlertAudioPrimingBound = true
  window.addEventListener('pointerdown', handleIdsAlertAudioPrimingGesture, {
    capture: true,
    passive: true,
  })
  window.addEventListener('keydown', handleIdsAlertAudioPrimingGesture, { capture: true })
  window.addEventListener('touchstart', handleIdsAlertAudioPrimingGesture, {
    capture: true,
    passive: true,
  })
}

export function unbindGlobalIdsAlertAudioPriming() {
  if (typeof window === 'undefined' || !idsAlertAudioPrimingBound) return
  idsAlertAudioPrimingBound = false
  window.removeEventListener('pointerdown', handleIdsAlertAudioPrimingGesture, true)
  window.removeEventListener('keydown', handleIdsAlertAudioPrimingGesture, true)
  window.removeEventListener('touchstart', handleIdsAlertAudioPrimingGesture, true)
}

export async function primeIdsAlertSound() {
  await primeIdsAlertSoundFromGesture()
}

export function readIdsAlertSoundSettings(): IDSAlertSoundSettings {
  return { ...FIXED_ALERT_SOUND_SETTINGS }
}

export function writeIdsAlertSoundSettings(
  _next: Partial<IDSAlertSoundSettings> | IDSAlertSoundSettings,
) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT))
  }
  return { ...FIXED_ALERT_SOUND_SETTINGS }
}

export async function getIdsAlertCustomSoundInfo(): Promise<IDSAlertSoundAssetInfo | null> {
  return { ...FIXED_ALERT_SOUND_INFO }
}

export async function saveIdsAlertCustomSound(_file: File) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT))
  }
  return { ...FIXED_ALERT_SOUND_INFO }
}

export async function clearIdsAlertCustomSound() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT))
  }
}

export function dispatchIDSFocusEvent(detail: IDSFocusEventDetail) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent<IDSFocusEventDetail>(IDS_ALERT_FOCUS_EVENT, { detail }))
}

export function stopIdsAlertAlarm() {
  idsAlertLoopRetryPending = false
  unbindIdsAlertPlaybackRetry()
  if (!activeAlertLoopAudio) return
  try {
    activeAlertLoopAudio.pause()
    activeAlertLoopAudio.currentTime = 0
  } catch {
    /* ignore media cleanup errors */
  }
  activeAlertLoopAudio = null
}

export async function startIdsAlertAlarm(_options?: { force?: boolean }) {
  stopIdsAlertAlarm()
  const audio = createAlertAudio(0.92)
  audio.loop = true
  audio.load()
  activeAlertLoopAudio = audio
  try {
    await audio.play()
    idsAlertAudioPrimed = true
    idsAlertLoopRetryPending = false
    unbindIdsAlertPlaybackRetry()
    return 'fixed'
  } catch (error) {
    idsAlertLoopRetryPending = true
    bindIdsAlertPlaybackRetry()
    throw error
  }
}

export async function playIdsAlertSound(_options?: { force?: boolean }) {
  const audio = createAlertAudio(0.92)
  audio.load()
  try {
    await audio.play()
    idsAlertAudioPrimed = true
    return 'fixed'
  } catch (error) {
    throw error
  }
}
