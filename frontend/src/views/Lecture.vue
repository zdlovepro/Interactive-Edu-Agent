<template>
  <div class="lecture-page">
    <section class="page-shell page-shell--wide page-section">
      <div class="lecture-layout">
        <div class="lecture-main">
          <DualTrackVideoStage
            ref="videoStageRef"
            class="lecture-video-stage"
            :video-src="lectureVideoUrl"
            :video-status="videoRenderTask?.status"
            :video-status-text="videoRenderStatusText"
            @timeupdate="handleVideoTimeUpdate"
            @play="handleVideoPlay"
            @pause="handleVideoPause"
          />

          <AppCard v-if="!isTeacherView" class="lecture-control-card" tone="subtle">
            <div class="control-grid">
              <div class="control-group control-group--voice">
                <span class="control-label">语音打断视频</span>
                <div class="control-row">
                  <AppButton
                    v-if="!voiceInterruptEnabled"
                    variant="secondary"
                    :disabled="!canUseVoiceInterrupt || lectureStore.isLoading"
                    @click="enableVoiceInterrupt"
                  >
                    开启语音打断
                  </AppButton>
                  <AppButton v-else variant="secondary" @click="disableVoiceInterrupt">
                    关闭语音打断
                  </AppButton>
                </div>

                <div class="voice-status-row">
                  <span class="voice-status-pill" :class="voiceStatusClass">
                    {{ voiceStatusText }}
                  </span>
                  <span class="voice-status-hint">{{ voiceStatusHint }}</span>
                  <span class="voice-status-hint">
                    {{ wsConnected ? '信令已连接，可自动同步打断状态' : '信令未连接，仍可手动提问' }}
                  </span>
                </div>

                <div class="voice-volume-meter" :class="{ active: voiceInterruptEnabled }">
                  <span class="voice-volume-bar" :style="{ transform: `scaleX(${voiceVolumeScale})` }"></span>
                </div>
              </div>
            </div>
          </AppCard>

          <LectureQuickQuiz
            v-if="slides.length && !isTeacherView"
            class="lecture-quiz-card"
            :slides="slides"
          />
        </div>

        <AppCard v-if="!isTeacherView" class="lecture-chat-panel" tone="glass">
          <div class="chat-header">
            <div>
              <span class="eyebrow">AI 助教问答</span>
              <h2>你可以针对整份课件内容提问</h2>
            </div>
            <span class="chat-header__status">{{ qaStatusText }}</span>
          </div>

          <div class="chat-history" ref="qaHistoryRef">
            <div v-if="qaList.length === 0" class="chat-empty">
              <h3>暂无问答记录，试着问一个问题吧。</h3>
              <p>系统会检索整份课件，并适度参考当前播放页位置，回答时同时展示参考 evidence。</p>
            </div>

            <div v-for="qa in qaList" :key="qa.id" class="chat-turn">
              <div class="bubble bubble--user">
                <span class="bubble-role">学生</span>
                <p>{{ qa.question }}</p>
              </div>

              <div class="bubble bubble--assistant">
                <span class="bubble-role">AI 助教</span>
                <div class="bubble-answer" v-html="renderMd(qa.answer)"></div>
                <div v-if="qa.streaming" class="bubble-streaming">
                  <span class="bubble-streaming__dot"></span>
                  <span>正在生成回答</span>
                </div>

                <details v-if="qa.evidence?.length" class="evidence-panel">
                  <summary>查看 evidence（{{ qa.evidence.length }}）</summary>
                  <div class="evidence-list">
                    <div
                      v-for="(evidence, index) in qa.evidence"
                      :key="`${qa.id}-${index}`"
                      class="evidence-item"
                    >
                      <div class="evidence-item__meta">
                        <span>{{ evidence.source || 'courseware' }}</span>
                        <span v-if="evidence.pageIndex">第 {{ evidence.pageIndex }} 页</span>
                      </div>
                      <p>{{ evidence.text }}</p>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </div>

          <div class="chat-composer">
            <label for="question-input" class="visually-hidden">输入问题</label>
            <input
              id="question-input"
              v-model="question"
              class="app-input"
              type="text"
              :disabled="isAsking"
              placeholder="输入你关于整份课件的问题，按 Enter 发送"
              @keyup.enter="submitQuestion"
            />
            <AppButton v-if="isStreamingAnswer" variant="secondary" @click="stopStreamingAnswer">
              停止生成
            </AppButton>
            <AppButton :disabled="!question.trim() || isAsking" @click="submitQuestion">
              {{ isAsking ? '思考中...' : '发送问题' }}
            </AppButton>
          </div>
        </AppCard>

        <AppCard v-else class="lecture-chat-panel teacher-panel" tone="glass">
          <div class="chat-header teacher-panel__header">
            <div>
              <span class="eyebrow">课程共享设置</span>
              <h2>在课堂页直接设置课程号</h2>
            </div>
            <span class="chat-header__status teacher-course-code-status">
              {{ currentCourseCodeStatusText }}
            </span>
          </div>

          <p class="teacher-panel__intro">
            为当前课件设置课程号后，学生即可在课堂资源页输入相同课程号访问这份课件。
          </p>

          <div class="teacher-course-code-form">
            <label for="teacher-course-code-input" class="teacher-course-code-label">课程号</label>
            <input
              id="teacher-course-code-input"
              v-model.trim="courseCodeInput"
              class="app-input"
              type="text"
              maxlength="64"
              :disabled="courseCodeLoading || !canManageCourseCode"
              placeholder="例如：ML-2026-A"
            />

            <div class="teacher-course-code-actions">
              <AppButton
                :disabled="courseCodeLoading || !canManageCourseCode || !isCourseCodeDirty"
                @click="saveCourseCode"
              >
                {{ courseCodeLoading ? '保存中...' : '保存课程号' }}
              </AppButton>
              <AppButton
                variant="secondary"
                :disabled="courseCodeLoading || !canManageCourseCode || !savedCourseCode"
                @click="clearCourseCode"
              >
                清除课程号
              </AppButton>
            </div>
          </div>

          <p class="teacher-panel__hint">
            {{ teacherCourseCodeHint }}
          </p>
        </AppCard>
      </div>
    </section>

    <div v-if="errorMsg" class="toast">
      <span>{{ errorMsg }}</span>
      <button @click="clearError">关闭</button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import DualTrackVideoStage from '@/components/lecture/DualTrackVideoStage.vue'
import LectureQuickQuiz from '@/components/lecture/LectureQuickQuiz.vue'
import {
  getCoursewareDetail,
  getCoursewareScript,
  getCoursewareVideoRenderTask,
  updateCoursewareCourseCode,
} from '@/api/courseware'
import { pauseLecture, resumeLecture, startLecture } from '@/api/lecture'
import { askText, streamAskText } from '@/api/qa'
import { COURSEWARE_VIDEO_API } from '@/constants/api'
import { LECTURE_STATE, normalizeLectureStatus } from '@/constants/lecture'
import { useAuthStore } from '@/stores/auth'
import { useLectureStore } from '@/stores/lecture'
import audioPlayer from '@/utils/audioPlayer'
import { createLecturePlaybackEngine } from '@/utils/lecturePlaybackEngine'
import { createLectureSocket } from '@/utils/lectureSocket'
import { createSpeechRecognizer } from '@/utils/speechRecognizer'
import { getErrorMessage } from '@/utils'

const route = useRoute()
const lectureStore = useLectureStore()
const authStore = useAuthStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const coursewareId = route.params.coursewareId
const routeCourseCode = computed(() => String(route.query.courseCode || '').trim().toUpperCase())

const slides = ref([])
const question = ref('')
const isAsking = ref(false)
const qaList = ref([])
const qaHistoryRef = ref(null)
const isSpeaking = ref(false)
const audioCurrentTime = ref(0)
const audioDuration = ref(0)
const isAudioPaused = ref(false)
const isSpeechPaused = ref(false)
const isContinuousPlayback = ref(false)
const canUseVoiceInterrupt = ref(false)
const voiceInterruptState = ref('off')
const voiceInterruptHint = ref('开启后会在检测到学生说话后自动打断当前视频播放')
const voiceDraftText = ref('')
const videoRenderTask = ref(null)
const videoCurrentTime = ref(0)
const videoDuration = ref(0)
const videoPaused = ref(true)
const videoStageRef = ref(null)
const courseCodeInput = ref('')
const savedCourseCode = ref('')
const coursewareAccessMode = ref('OWNED')
const courseCodeLoading = ref(false)
const hasPausedForVoiceInterrupt = ref(false)

const VOICE_INTERRUPT_STATE = {
  OFF: 'off',
  LISTENING: 'listening',
  RECORDING: 'recording',
  COMPLETED: 'completed',
  UNAVAILABLE: 'unavailable',
}

const failedAudioUrls = new Set()
const audioUnsubscribers = []
let speechUtterance = null
let manualSpeechStopRequested = false
let playbackEngine = null
let lectureSocket = null
let socketMessageUnsubscribe = null
let socketErrorUnsubscribe = null
let hasShownSocketError = false
let speechRecognizer = null
let qaStreamClient = null
let activeStreamingQaItemId = null
let videoRenderPollTimer = null
let voiceRecognizerRestartTimer = null
let suspendVoiceRecognition = false

const lectureStatus = computed(() => normalizeLectureStatus(lectureStore.status))
const playbackMode = computed(() => lectureStore.audioMode)
const currentPage = computed(() => lectureStore.currentPage)
const currentSlide = computed(() => slides.value[currentPage.value - 1] || null)
const voiceInterruptEnabled = computed(() => lectureStore.vadEnabled)
const isVoiceRecording = computed(() => lectureStore.isRecording)
const isStreamingAnswer = computed(() => lectureStore.isStreamingAnswer)
const wsConnected = computed(() => lectureStore.wsConnected)
const errorMsg = computed(() => lectureStore.errorMessage)
const useAudioPlayback = computed(
  () => Boolean(currentSlide.value?.audioUrl) && !failedAudioUrls.has(currentSlide.value.audioUrl),
)
const videoTimeline = computed(() => {
  if (!Array.isArray(videoRenderTask.value?.timeline)) {
    return []
  }

  return videoRenderTask.value.timeline
    .map(item => ({
      pageIndex: Number(item?.pageIndex) || 0,
      startMs: Number(item?.startMs) || 0,
      endMs: Number(item?.endMs) || 0,
      title: item?.title || '',
    }))
    .filter(item => item.pageIndex > 0 && item.endMs >= item.startMs)
    .sort((left, right) => left.startMs - right.startMs)
})
const videoContextPageIndex = computed(() => resolveVideoContextPageIndex(videoCurrentTime.value))
const qaContextPageIndex = computed(() => {
  const shouldUseVideoContext =
    videoTimeline.value.length > 0 && (videoCurrentTime.value > 0 || videoDuration.value > 0 && !videoPaused.value)
  return shouldUseVideoContext ? videoContextPageIndex.value || currentPage.value : currentPage.value
})
const qaStatusText = computed(() =>
  isStreamingAnswer.value
    ? `生成中 · 全课件检索 · 当前定位第 ${qaContextPageIndex.value} 页`
    : `全课件上下文 · 当前定位第 ${qaContextPageIndex.value} 页`,
)
const isTeacherView = computed(() => authStore.isTeacher)
const canManageCourseCode = computed(
  () => isTeacherView.value && coursewareAccessMode.value !== 'SHARED',
)
const normalizedCourseCodeInput = computed(() => normalizeCourseCodeInput(courseCodeInput.value))
const isCourseCodeDirty = computed(
  () => normalizedCourseCodeInput.value !== normalizeCourseCodeInput(savedCourseCode.value),
)
const currentCourseCodeStatusText = computed(() =>
  savedCourseCode.value ? `当前课程号 · ${savedCourseCode.value}` : '当前未设置课程号',
)
const teacherCourseCodeHint = computed(() =>
  canManageCourseCode.value
    ? '建议使用稳定、易记的课程缩写。保存后，学生即可通过该课程号访问当前课件。'
    : '当前课件属于共享访问状态，不能在课堂页修改课程号。',
)
const lectureVideoUrl = computed(() => {
  if (String(videoRenderTask.value?.status || '').toUpperCase() !== 'READY') {
    return ''
  }

  if (videoRenderTask.value?.hlsUrl) {
    return buildApiUrl(videoRenderTask.value.hlsUrl)
  }

  return buildApiUrl(COURSEWARE_VIDEO_API.SOURCE(coursewareId))
})
const hasPlayableVideo = computed(() => Boolean(lectureVideoUrl.value))
const videoRenderStatusText = computed(() => {
  const status = String(videoRenderTask.value?.status || '').toUpperCase()

  if (!status) {
    return '当前课件还没有可播放的生成视频，请先到讲稿页触发视频生成。'
  }

  if (status === 'READY') {
    return '课堂页现在展示的是真实生成视频，不再使用示例视频素材。'
  }

  if (status === 'RENDERING' || status === 'PENDING') {
    return videoRenderTask.value?.message || '讲解视频正在生成中，完成后这里会自动切换到可播放视频。'
  }

  if (status === 'FAILED') {
    return videoRenderTask.value?.errorMessage || '视频生成失败，请回到讲稿页重新触发渲染。'
  }

  return '当前课件还没有可播放的生成视频，请先到讲稿页触发视频生成。'
})
const voiceStatusText = computed(() => {
  switch (voiceInterruptState.value) {
    case VOICE_INTERRUPT_STATE.LISTENING:
      return '正在倾听'
    case VOICE_INTERRUPT_STATE.RECORDING:
      return '正在录音'
    case VOICE_INTERRUPT_STATE.COMPLETED:
      return '录音完成'
    case VOICE_INTERRUPT_STATE.UNAVAILABLE:
      return '麦克风不可用'
    default:
      return voiceInterruptEnabled.value ? '已开启' : '未开启'
  }
})
const voiceStatusHint = computed(() => voiceInterruptHint.value)
const voiceStatusClass = computed(() => `voice-status-pill--${voiceInterruptState.value}`)
const voiceVolumeScale = computed(() => {
  if (!voiceInterruptEnabled.value) {
    return 0.04
  }

  switch (voiceInterruptState.value) {
    case VOICE_INTERRUPT_STATE.LISTENING:
      return 0.32
    case VOICE_INTERRUPT_STATE.RECORDING:
      return 0.78
    case VOICE_INTERRUPT_STATE.COMPLETED:
      return 0.55
    default:
      return 0.12
  }
})

const buildApiUrl = path => {
  if (!path) {
    return API_BASE_URL
  }

  if (/^https?:\/\//i.test(path)) {
    return path
  }

  const normalizedBase = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  if (normalizedPath === normalizedBase || normalizedPath.startsWith(`${normalizedBase}/`)) {
    return normalizedPath
  }
  return `${normalizedBase}${normalizedPath}`
}

const normalizeCourseCodeInput = value => String(value || '').trim().toUpperCase()

const applyCoursewareMeta = payload => {
  coursewareAccessMode.value = String(payload?.accessMode || 'OWNED')
    .trim()
    .toUpperCase()
  savedCourseCode.value = normalizeCourseCodeInput(payload?.courseCode || '')
  courseCodeInput.value = savedCourseCode.value
}

const resolveVideoContextPageIndex = currentTimeSeconds => {
  if (!videoTimeline.value.length) {
    return null
  }

  const currentMs = Math.max(0, Math.floor((Number(currentTimeSeconds) || 0) * 1000))
  const matched = videoTimeline.value.find(item => currentMs >= item.startMs && currentMs < item.endMs)
  if (matched) {
    return matched.pageIndex
  }

  if (currentMs <= videoTimeline.value[0].startMs) {
    return videoTimeline.value[0].pageIndex
  }

  return videoTimeline.value[videoTimeline.value.length - 1].pageIndex
}

const getQuestionContextPageIndex = () => qaContextPageIndex.value

const updateVideoPlaybackState = payload => {
  if (!payload || typeof payload !== 'object') {
    return
  }

  videoCurrentTime.value = Number(payload.currentTime) || 0
  videoDuration.value = Number(payload.duration) || 0
  videoPaused.value = payload.paused !== false
}

const handleVideoTimeUpdate = payload => {
  updateVideoPlaybackState(payload)
}

const handleVideoPlay = payload => {
  updateVideoPlaybackState(payload)
  videoPaused.value = false
}

const handleVideoPause = payload => {
  updateVideoPlaybackState(payload)
  videoPaused.value = true
}

const pauseVideoPlayback = () => {
  if (!hasPlayableVideo.value || !videoStageRef.value || videoPaused.value) {
    return false
  }

  const currentTime = Number(videoStageRef.value.getCurrentTime?.())
  if (Number.isFinite(currentTime) && currentTime >= 0) {
    videoCurrentTime.value = currentTime
  }

  videoStageRef.value.pause?.()
  videoPaused.value = true
  return true
}

const resumeVideoPlayback = async ({ seekTime } = {}) => {
  if (!hasPlayableVideo.value || !videoStageRef.value) {
    return false
  }

  const targetTime = Number(seekTime)
  if (Number.isFinite(targetTime) && targetTime >= 0) {
    const duration = Number(videoStageRef.value.getDuration?.()) || videoDuration.value
    videoStageRef.value.seek?.(clampBreakpointTime(targetTime, duration))
  }

  await videoStageRef.value.play?.()
  videoPaused.value = false
  lectureStore.setStatus(LECTURE_STATE.PLAYING)
  return true
}

const clampBreakpointTime = (seconds, duration = 0) => {
  const value = Number(seconds)
  if (!Number.isFinite(value) || value < 0) {
    return 0
  }

  if (!Number.isFinite(duration) || duration <= 0) {
    return value
  }

  if (value > duration) {
    return Math.max(duration - 0.5, 0)
  }

  return value
}

const renderMd = text => {
  if (!text) {
    return ''
  }
  return marked.parse(text, { breaks: true })
}

const clearError = () => {
  lectureStore.setErrorMessage('')
}

const showError = (error, fallback) => {
  lectureStore.setErrorMessage(getErrorMessage(error, fallback))
}

const stopVideoRenderPolling = () => {
  if (videoRenderPollTimer) {
    window.clearInterval(videoRenderPollTimer)
    videoRenderPollTimer = null
  }
}

const fetchVideoRenderTask = async ({ silent = true } = {}) => {
  try {
    const response = await getCoursewareVideoRenderTask(coursewareId)
    videoRenderTask.value = response.data || null

    const status = String(videoRenderTask.value?.status || '').toUpperCase()
    if (status === 'PENDING' || status === 'RENDERING') {
      if (!videoRenderPollTimer) {
        videoRenderPollTimer = window.setInterval(async () => {
          const nextTask = await fetchVideoRenderTask({ silent: true })
          const nextStatus = String(nextTask?.status || '').toUpperCase()
          if (!nextTask || (nextStatus !== 'PENDING' && nextStatus !== 'RENDERING')) {
            stopVideoRenderPolling()
          }
        }, 3000)
      }
    } else {
      stopVideoRenderPolling()
    }

    return videoRenderTask.value
  } catch (error) {
    videoRenderTask.value = null
    stopVideoRenderPolling()
    if (!silent) {
      showError(error, '无法获取讲解视频状态，请稍后重试。')
    }
    return null
  }
}

const loadCoursewareMeta = async ({ silent = true } = {}) => {
  try {
    const response = await getCoursewareDetail(coursewareId)
    applyCoursewareMeta(response.data)
    return response.data || null
  } catch (error) {
    coursewareAccessMode.value = 'OWNED'
    if (!silent) {
      showError(error, '无法加载当前课件的课程号信息，请稍后重试。')
    }
    return null
  }
}

const handleSocketMessage = message => {
  if (!message || typeof message !== 'object') {
    return
  }

  if (message.type === 'connection') {
    const isOpen = message.payload?.status === 'open'
    lectureStore.setWsConnected(isOpen)
    if (isOpen) {
      hasShownSocketError = false
    }
    return
  }

  lectureStore.setWsConnected(true)

  if (message.type === 'ack') {
    const payload = message.payload || {}
    const breakpointTime = payload.currentTime ?? payload.breakpointTime

    if (payload.status) {
      lectureStore.setStatus(payload.status)
    }

    if (payload.pageIndex) {
      lectureStore.setCurrentPage(payload.pageIndex)
    }

    if (breakpointTime !== undefined && payload.pageIndex) {
      lectureStore.setBreakpoint(payload.pageIndex, breakpointTime)
    }

    if (payload.status === LECTURE_STATE.INTERRUPTED) {
      updateVoiceInterruptState(VOICE_INTERRUPT_STATE.RECORDING, '已暂停讲解，正在倾听')
    }
    return
  }

  if (message.type === 'state') {
    const payload = message.payload || {}

    if (payload.status) {
      lectureStore.setStatus(payload.status)
    }

    if (payload.currentNode) {
      lectureStore.setCurrentNode(payload.currentNode)
    } else if (payload.pageIndex) {
      syncCurrentNodeWithSlide(payload.pageIndex)
    }

    if (payload.currentTime !== undefined && payload.pageIndex) {
      lectureStore.setBreakpoint(payload.pageIndex, payload.currentTime)
    }
    return
  }

  if (message.type === 'error') {
    const messageText = message.payload?.message || '信令连接失败，可继续手动提问。'
    showError(messageText, messageText)
  }
}

const handleSocketError = error => {
  lectureStore.setWsConnected(false)
  if (hasShownSocketError) {
    return
  }

  hasShownSocketError = true
  showError(error, '信令连接失败，可继续手动提问。')
}

const ensureLectureSocket = () => {
  if (lectureSocket) {
    return lectureSocket
  }

  lectureSocket = createLectureSocket()
  socketMessageUnsubscribe = lectureSocket.onMessage(handleSocketMessage)
  socketErrorUnsubscribe = lectureSocket.onError(handleSocketError)
  return lectureSocket
}

const connectLectureSocket = async sessionId => {
  if (!sessionId) {
    return false
  }

  try {
    await ensureLectureSocket().connect(sessionId)
    lectureStore.setWsConnected(true)
    hasShownSocketError = false
    return true
  } catch (error) {
    handleSocketError(error)
    return false
  }
}

const disconnectLectureSocket = () => {
  lectureStore.setWsConnected(false)
  socketMessageUnsubscribe?.()
  socketErrorUnsubscribe?.()
  socketMessageUnsubscribe = null
  socketErrorUnsubscribe = null
  lectureSocket?.close()
  lectureSocket = null
}

const sendLectureSignal = (type, payload = {}) => {
  if (!lectureStore.sessionId) {
    return false
  }

  try {
    return ensureLectureSocket().send(type, {
      sessionId: lectureStore.sessionId,
      ...payload,
    })
  } catch (error) {
    handleSocketError(error)
    return false
  }
}

const supportsVoiceInterrupt = () =>
  Boolean(globalThis.navigator?.mediaDevices?.getUserMedia) &&
  Boolean(globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition)

const updateVoiceInterruptState = (state, hint) => {
  voiceInterruptState.value = state
  if (hint !== undefined) {
    voiceInterruptHint.value = hint
  }
}

const clearVoiceRecognizerRestartTimer = () => {
  if (voiceRecognizerRestartTimer) {
    window.clearTimeout(voiceRecognizerRestartTimer)
    voiceRecognizerRestartTimer = null
  }
}

const handleMicrophoneError = error => {
  const permissionDenied =
    error?.name === 'NotAllowedError' ||
    error?.name === 'PermissionDeniedError' ||
    error?.message?.includes('权限')

  const unsupported = error?.message?.includes('不支持')
  const message = permissionDenied
    ? '无法访问麦克风，请检查浏览器权限，或手动输入问题。'
    : unsupported
      ? '当前浏览器不支持语音打断，请改用手动输入问题。'
      : getErrorMessage(error, '无法启用语音打断，请稍后重试。')

  updateVoiceInterruptState(
    unsupported ? VOICE_INTERRUPT_STATE.UNAVAILABLE : VOICE_INTERRUPT_STATE.OFF,
    message,
  )
  lectureStore.setVadEnabled(false)
  lectureStore.setRecording(false)
  showError(message, message)
}

const syncVoiceDraftText = transcript => {
  const normalizedText = String(transcript || '').trim()
  voiceDraftText.value = normalizedText
  lectureStore.setLastRecognizedText(normalizedText)
  if (normalizedText) {
    question.value = normalizedText
  }
  return normalizedText
}

const pausePlaybackForVoiceInterrupt = () => {
  if (lectureStatus.value === LECTURE_STATE.ENDED || lectureStatus.value === LECTURE_STATE.ANSWERING) {
    return false
  }

  const breakpointTime =
    hasPlayableVideo.value && !videoPaused.value
      ? videoCurrentTime.value
      : playbackMode.value === 'audio'
        ? audioPlayer.getCurrentTime()
        : audioCurrentTime.value
  const contextPageIndex = getQuestionContextPageIndex()

  pauseCurrentPlayback()
  lectureStore.pauseForInterrupt(breakpointTime, contextPageIndex)
  sendLectureSignal('interrupt', {
    pageIndex: contextPageIndex,
    currentTime: breakpointTime,
  })
  return true
}

const handleVoiceRecognitionResult = ({ transcript, finalTranscript, interimTranscript, hasFinal } = {}) => {
  if (!voiceInterruptEnabled.value) {
    return
  }

  const normalizedText = syncVoiceDraftText(transcript || finalTranscript || interimTranscript)
  if (!normalizedText) {
    return
  }

  if (!hasPausedForVoiceInterrupt.value) {
    hasPausedForVoiceInterrupt.value = true
    pausePlaybackForVoiceInterrupt()
  }

  updateVoiceInterruptState(
    VOICE_INTERRUPT_STATE.RECORDING,
    hasFinal
      ? '已识别到问题内容，讲解已暂停，可继续补充或再次点击按钮结束识别。'
      : '正在识别你的问题，讲解已暂停，请继续说完。',
  )
}

const restartVoiceInterruptListening = () => {
  clearVoiceRecognizerRestartTimer()
  if (!voiceInterruptEnabled.value) {
    return
  }

  voiceRecognizerRestartTimer = window.setTimeout(() => {
    try {
      ensureSpeechRecognizer().start()
    } catch (error) {
      handleVoiceRecognitionError(error)
    }
  }, 320)
}

const handleVoiceRecognitionEnd = ({ manualStop = false } = {}) => {
  lectureStore.setRecording(false)
  clearVoiceRecognizerRestartTimer()

  if (suspendVoiceRecognition) {
    suspendVoiceRecognition = false
    updateVoiceInterruptState(
      voiceInterruptEnabled.value ? VOICE_INTERRUPT_STATE.OFF : VOICE_INTERRUPT_STATE.COMPLETED,
      voiceInterruptEnabled.value
        ? '语音打断已暂停，恢复课堂后会重新开始监听。'
        : '语音识别已结束，可在右侧输入框中检查并发送问题。',
    )
    return
  }

  if (!voiceInterruptEnabled.value || manualStop) {
    const hasText = Boolean(voiceDraftText.value.trim())
    updateVoiceInterruptState(
      hasText ? VOICE_INTERRUPT_STATE.COMPLETED : VOICE_INTERRUPT_STATE.OFF,
      hasText
        ? '识别结束，问题已填入右侧输入框，可以直接发送给 AI。'
        : '语音打断已关闭，可重新开启后再试。',
    )
    return
  }

  restartVoiceInterruptListening()
}

const handleVoiceRecognitionError = error => {
  const code = String(error?.code || error?.name || '').trim().toLowerCase()
  lectureStore.setRecording(false)

  if (code === 'aborted') {
    return
  }

  if (code === 'no-speech') {
    updateVoiceInterruptState(
      hasPausedForVoiceInterrupt.value ? VOICE_INTERRUPT_STATE.RECORDING : VOICE_INTERRUPT_STATE.LISTENING,
      hasPausedForVoiceInterrupt.value
        ? '暂未识别到新的语音内容，可继续说话或再次点击按钮结束识别。'
        : '正在倾听，请开始说出你的问题。',
    )
    return
  }

  clearVoiceRecognizerRestartTimer()
  lectureStore.setVadEnabled(false)
  const message = getErrorMessage(error, '语音识别暂时不可用，请稍后重试。')
  updateVoiceInterruptState(VOICE_INTERRUPT_STATE.UNAVAILABLE, message)
  showError(message, message)
}

const ensureSpeechRecognizer = () => {
  if (speechRecognizer) {
    return speechRecognizer
  }

  speechRecognizer = createSpeechRecognizer({
    lang: 'zh-CN',
    continuous: true,
    interimResults: true,
    onStart: () => {
      lectureStore.setRecording(true)
      updateVoiceInterruptState(
        hasPausedForVoiceInterrupt.value ? VOICE_INTERRUPT_STATE.RECORDING : VOICE_INTERRUPT_STATE.LISTENING,
        hasPausedForVoiceInterrupt.value
          ? '正在识别你的问题，请继续说完，然后再次点击按钮结束。'
          : '正在倾听，识别到问题文字后会暂停当前讲解。',
      )
    },
    onResult: payload => {
      handleVoiceRecognitionResult(payload)
    },
    onEnd: payload => {
      handleVoiceRecognitionEnd(payload)
    },
    onError: error => {
      handleVoiceRecognitionError(error)
    },
  })

  return speechRecognizer
}

const beginVoiceInterruptMonitoring = async ({ force = false } = {}) => {
  if (!voiceInterruptEnabled.value || !canUseVoiceInterrupt.value || lectureStatus.value === LECTURE_STATE.ENDED) {
    return false
  }

  try {
    if (force) {
      syncVoiceDraftText('')
      hasPausedForVoiceInterrupt.value = false
      suspendVoiceRecognition = false
      if (voiceInterruptState.value === VOICE_INTERRUPT_STATE.COMPLETED) {
        updateVoiceInterruptState(VOICE_INTERRUPT_STATE.OFF, '语音打断已恢复，正在重新进入监听。')
      }
    }

    const stream = await globalThis.navigator.mediaDevices.getUserMedia({ audio: true })
    stream.getTracks().forEach(track => track.stop())

    const started = ensureSpeechRecognizer().start()
    if (!started && !isVoiceRecording.value) {
      updateVoiceInterruptState(
        hasPausedForVoiceInterrupt.value ? VOICE_INTERRUPT_STATE.RECORDING : VOICE_INTERRUPT_STATE.LISTENING,
        hasPausedForVoiceInterrupt.value
          ? '正在继续识别你刚才的问题，请说完后再次点击按钮结束识别。'
          : '正在监听，识别到文字后会自动暂停当前视频。',
      )
    }
    return true
  } catch (error) {
    handleMicrophoneError(error)
    return false
  }
}

const enableVoiceInterrupt = async () => {
  clearError()

  if (!canUseVoiceInterrupt.value) {
    handleMicrophoneError(new Error('当前浏览器不支持语音打断，请改用手动输入问题。'))
    return
  }

  lectureStore.setVadEnabled(true)
  lectureStore.setRecording(false)
  lectureStore.clearBreakpoint()
  syncVoiceDraftText('')
  hasPausedForVoiceInterrupt.value = false
  await beginVoiceInterruptMonitoring({ force: true })
}

const disableVoiceInterrupt = async () => {
  clearVoiceRecognizerRestartTimer()
  lectureStore.setVadEnabled(false)
  lectureStore.setRecording(false)
  const stopped = speechRecognizer?.stop?.() ?? false

  if (!stopped) {
    const hasText = Boolean(voiceDraftText.value.trim())
    updateVoiceInterruptState(
      hasText ? VOICE_INTERRUPT_STATE.COMPLETED : VOICE_INTERRUPT_STATE.OFF,
      hasText
        ? '语音识别已结束，可在右侧输入框中检查并发送问题。'
        : '语音打断已关闭。',
    )
  }
}

const resetAudioProgress = () => {
  audioCurrentTime.value = 0
  audioDuration.value = 0
}

const resetPauseFlags = () => {
  isAudioPaused.value = false
  isSpeechPaused.value = false
}

const haltPlayback = () => {
  audioPlayer.stop()

  if (globalThis.speechSynthesis) {
    if (globalThis.speechSynthesis.speaking || globalThis.speechSynthesis.pending || globalThis.speechSynthesis.paused) {
      manualSpeechStopRequested = true
      globalThis.speechSynthesis.cancel()
    }
  }

  speechUtterance = null
  isSpeaking.value = false
  resetPauseFlags()
  resetAudioProgress()
}

const pauseCurrentPlayback = () => {
  if (pauseVideoPlayback()) {
    isSpeaking.value = false
    return
  }

  if (playbackMode.value === 'audio' && (isSpeaking.value || audioCurrentTime.value > 0)) {
    audioPlayer.pause()
    isAudioPaused.value = true
    isSpeaking.value = false
    return
  }

  if (playbackMode.value === 'speech' && globalThis.speechSynthesis?.speaking) {
    globalThis.speechSynthesis.pause()
    isSpeechPaused.value = true
    isSpeaking.value = false
  }
}

const resumeCurrentPlayback = async () => {
  if (hasPlayableVideo.value && videoPaused.value) {
    try {
      await resumeVideoPlayback({ seekTime: videoCurrentTime.value })
      return true
    } catch (error) {
      showError(error, '浏览器阻止了视频继续播放，请手动恢复视频播放。')
      return false
    }
  }

  if (playbackMode.value === 'audio' && isAudioPaused.value) {
    try {
      await audioPlayer.resume()
      isAudioPaused.value = false
      isSpeaking.value = true
      lectureStore.setStatus(LECTURE_STATE.PLAYING)
      return true
    } catch (error) {
      showError(error, '浏览器阻止了自动播放，请手动恢复视频播放。')
      return false
    }
  }

  if (playbackMode.value === 'speech' && isSpeechPaused.value && globalThis.speechSynthesis?.paused) {
    globalThis.speechSynthesis.resume()
    isSpeechPaused.value = false
    isSpeaking.value = true
    lectureStore.setStatus(LECTURE_STATE.PLAYING)
    return true
  }

  return false
}

const restorePlaybackFromBreakpoint = async ({ pageIndex, breakpointTime } = {}) => {
  const targetPage = Number(pageIndex)
  if (!Number.isFinite(targetPage) || targetPage <= 0) {
    lectureStore.setStatus(LECTURE_STATE.INTERRUPTED)
    return false
  }

  const slide = slides.value[targetPage - 1]
  if (!slide?.content) {
    lectureStore.setStatus(LECTURE_STATE.INTERRUPTED)
    return false
  }

  if (hasPlayableVideo.value) {
    syncToPage(targetPage)

    try {
      await resumeVideoPlayback({ seekTime: breakpointTime })
      return true
    } catch (error) {
      if (error?.name === 'NotAllowedError') {
        showError(error, '浏览器阻止了视频继续播放，请手动恢复视频播放。')
        return false
      }
    }
  }

  const canResumeCurrentAudio =
    playbackMode.value === 'audio' && isAudioPaused.value && currentPage.value === targetPage

  syncToPage(targetPage)

  if (!slide.audioUrl || failedAudioUrls.has(slide.audioUrl)) {
    lectureStore.setAudioMode('speech')
    resetPauseFlags()
    isSpeaking.value = false
    audioCurrentTime.value = 0
    audioDuration.value = 0
    lectureStore.setStatus(LECTURE_STATE.PLAYING)
    return true
  }

  try {
    if (!canResumeCurrentAudio) {
      await audioPlayer.load(slide.audioUrl)
    }

    const duration = audioPlayer.getDuration()
    const targetTime = clampBreakpointTime(breakpointTime, duration)

    lectureStore.setAudioMode('audio')
    resetPauseFlags()
    audioDuration.value = duration
    audioPlayer.seek(targetTime)
    audioCurrentTime.value = targetTime

    if (canResumeCurrentAudio) {
      await audioPlayer.resume()
    } else {
      await audioPlayer.play()
    }

    isSpeaking.value = true
    isAudioPaused.value = false
    lectureStore.setStatus(LECTURE_STATE.PLAYING)
    return true
  } catch (error) {
    if (error?.name === 'NotAllowedError') {
      showError(error, '浏览器阻止了自动播放，请手动恢复视频播放。')
      haltPlayback()
      return false
    }

    failedAudioUrls.add(slide.audioUrl)
    showError('音频资源加载失败，已切换备用讲解链路。', '音频资源加载失败，已切换备用讲解链路。')
    lectureStore.setAudioMode('speech')
    lectureStore.setStatus(LECTURE_STATE.PLAYING)
    return true
  }
}

const syncCurrentNodeWithSlide = page => {
  const slide = slides.value[page - 1]
  if (!slide) {
    return
  }

  lectureStore.setCurrentNode({
    nodeId: slide.nodeId || slide.id,
    pageIndex: slide.pageIndex || page,
    content: slide.content,
    audioUrl: slide.audioUrl || null,
  })
}

const syncToPage = page => {
  lectureStore.setCurrentPage(page)
  syncCurrentNodeWithSlide(page)
  lectureStore.setAudioMode(slides.value[page - 1]?.audioUrl ? 'audio' : 'speech')
}

const speakWithBrowser = text => {
  if (!text || !globalThis.speechSynthesis) {
    return
  }

  lectureStore.setAudioMode('speech')
  resetAudioProgress()
  resetPauseFlags()
  manualSpeechStopRequested = false

  speechUtterance = new SpeechSynthesisUtterance(text)
  speechUtterance.lang = 'zh-CN'
  speechUtterance.rate = 1
  speechUtterance.onend = async () => {
    const manualStop = manualSpeechStopRequested
    manualSpeechStopRequested = false
    isSpeaking.value = false
    resetPauseFlags()

    if (manualStop) {
      return
    }

    await playbackEngine?.handlePlaybackEnded()
  }
  speechUtterance.onerror = () => {
    manualSpeechStopRequested = false
    isSpeaking.value = false
    resetPauseFlags()
  }

  globalThis.speechSynthesis.speak(speechUtterance)
  isSpeaking.value = true
  lectureStore.setStatus(LECTURE_STATE.PLAYING)
}

const fallbackToSpeech = text => {
  haltPlayback()
  speakWithBrowser(text)
}

const playCurrentSlideByPageIndex = async pageIndex => {
  const slide = slides.value[pageIndex - 1]
  if (!slide?.content) {
    return false
  }

  haltPlayback()

  if (!slide.audioUrl || failedAudioUrls.has(slide.audioUrl)) {
    fallbackToSpeech(slide.content)
    return true
  }

  lectureStore.setAudioMode('audio')
  resetPauseFlags()

  try {
    await audioPlayer.load(slide.audioUrl)
    audioDuration.value = audioPlayer.getDuration()
    audioCurrentTime.value = audioPlayer.getCurrentTime()
    await audioPlayer.play()
    isSpeaking.value = true
    lectureStore.setStatus(LECTURE_STATE.PLAYING)
    return true
  } catch (error) {
    if (error?.name === 'NotAllowedError') {
      showError(error, '浏览器阻止了自动播放，请手动恢复视频播放。')
      haltPlayback()
      return false
    }

    failedAudioUrls.add(slide.audioUrl)
    showError('音频资源加载失败，已切换备用讲解链路。', '音频资源加载失败，已切换备用讲解链路。')
    fallbackToSpeech(slide.content)
    return true
  }
}

const normalizeSlide = (segment, index) => ({
  id: segment?.id || segment?.nodeId || `segment-${index + 1}`,
  nodeId: segment?.nodeId || segment?.id || `node-${index + 1}`,
  pageIndex: Number(segment?.pageIndex || index + 1),
  title: segment?.title || `第 ${index + 1} 页`,
  content: segment?.content || '',
  knowledgePoints: Array.isArray(segment?.knowledgePoints) ? segment.knowledgePoints : [],
  audioUrl: segment?.audioUrl || null,
  pageImagePath: segment?.pageImagePath || null,
  visualSummary: segment?.visualSummary || '',
  visualObjects: Array.isArray(segment?.visualObjects) ? segment.visualObjects : [],
})

const loadSlides = async () => {
  lectureStore.setLoading(true)
  clearError()

  try {
    const response = await getCoursewareScript(coursewareId)
    const segments = Array.isArray(response.data?.segments) ? response.data.segments : []

    if (!segments.length) {
      slides.value = []
      showError(null, '讲稿为空，请先生成讲稿后再进入课堂。')
      return false
    }

    slides.value = segments.map(normalizeSlide)
    syncToPage(1)
    lectureStore.setStatus(LECTURE_STATE.IDLE)
    return true
  } catch (error) {
    slides.value = []
    showError(error, '无法加载课堂讲稿，请稍后重试。')
    return false
  } finally {
    lectureStore.setLoading(false)
  }
}

const startLectureSession = async () => {
  lectureStore.setLoading(true)
  clearError()

  try {
    lectureStore.setCoursewareId(coursewareId)
    const response = await startLecture({ coursewareId })
    lectureStore.syncFromStartResponse({
      ...response.data,
      coursewareId,
    })
    if (!response.data?.currentNode?.pageIndex) {
      syncCurrentNodeWithSlide(currentPage.value)
    }
    await connectLectureSocket(lectureStore.sessionId)
  } catch (error) {
    showError(error, '无法开始课堂，请稍后重试。')
  } finally {
    lectureStore.setLoading(false)
  }
}

const togglePlayback = async () => {
  if (!currentSlide.value) {
    return
  }

  if (isSpeaking.value || isAudioPaused.value || isSpeechPaused.value || (hasPlayableVideo.value && !videoPaused.value)) {
    playbackEngine?.stopCurrentPage()
    if (voiceInterruptEnabled.value && speechRecognizer?.isListening) {
      suspendVoiceRecognition = true
      speechRecognizer.stop()
    }
    if (voiceInterruptEnabled.value) {
      updateVoiceInterruptState(VOICE_INTERRUPT_STATE.OFF, '语音打断已暂停，等待恢复播放后重新监听。')
    }
    lectureStore.setStatus(LECTURE_STATE.IDLE)
    return
  }

  lectureStore.setStatus(LECTURE_STATE.PLAYING)
  await playbackEngine?.playPage(currentPage.value)
  if (voiceInterruptEnabled.value) {
    await beginVoiceInterruptMonitoring({ force: true })
  }
}

const handlePauseLecture = async () => {
  if (!lectureStore.sessionId) {
    return
  }

  lectureStore.setLoading(true)
  clearError()
  const hadActivePlayback =
    isSpeaking.value ||
    isAudioPaused.value ||
    isSpeechPaused.value ||
    audioCurrentTime.value > 0 ||
    (hasPlayableVideo.value && !videoPaused.value)
  pauseCurrentPlayback()
  if (voiceInterruptEnabled.value && speechRecognizer?.isListening) {
    suspendVoiceRecognition = true
    speechRecognizer.stop()
  }
  if (voiceInterruptEnabled.value) {
    updateVoiceInterruptState(VOICE_INTERRUPT_STATE.OFF, '课堂已暂停，恢复后会重新开始监听。')
  }

  try {
    const response = await pauseLecture(lectureStore.sessionId)
    lectureStore.setStatus(response.data?.status)
  } catch (error) {
    showError(error, '暂停课堂失败，请稍后重试。')
    if (hadActivePlayback) {
      await resumeCurrentPlayback()
    }
  } finally {
    lectureStore.setLoading(false)
  }
}

const handleResumeLecture = async () => {
  if (!lectureStore.sessionId) {
    return
  }

  lectureStore.setLoading(true)
  clearError()
  sendLectureSignal('resume')
  lectureStore.resumeFromBreakpoint()
  suspendVoiceRecognition = false

  try {
    const response = await resumeLecture({ sessionId: lectureStore.sessionId })
    const responsePageIndex = response.data?.pageIndex || response.data?.currentNode?.pageIndex || lectureStore.breakpointPage
    const responseBreakpointTime = response.data?.breakpointTime ?? lectureStore.breakpointTime
    lectureStore.syncFromStartResponse({
      ...response.data,
      coursewareId,
    })
    if (responsePageIndex) {
      lectureStore.setBreakpoint(responsePageIndex, responseBreakpointTime)
    }

    if (!response.data?.currentNode?.pageIndex && responsePageIndex) {
      syncCurrentNodeWithSlide(responsePageIndex)
    }

    const resumed = await restorePlaybackFromBreakpoint({
      pageIndex: lectureStore.breakpointPage,
      breakpointTime: lectureStore.breakpointTime,
    })

    if (!resumed && lectureStore.breakpointPage) {
      syncCurrentNodeWithSlide(lectureStore.breakpointPage)
    }

    if (resumed) {
      lectureStore.clearBreakpoint()
    }

    if (resumed && voiceInterruptEnabled.value) {
      await beginVoiceInterruptMonitoring({ force: true })
    }
  } catch (error) {
    if (lectureStore.breakpointPage) {
      lectureStore.setStatus(LECTURE_STATE.INTERRUPTED)
    }
    showError(error, '继续课堂失败，请稍后重试。')
  } finally {
    lectureStore.setLoading(false)
  }
}

const restoreLectureStatusAfterAnswer = () => {
  if (lectureStore.breakpointPage) {
    lectureStore.setStatus(LECTURE_STATE.INTERRUPTED)
    return
  }

  if (lectureStatus.value === LECTURE_STATE.ENDED) {
    return
  }

  if (isSpeaking.value || isAudioPaused.value || isSpeechPaused.value) {
    lectureStore.setStatus(LECTURE_STATE.PLAYING)
    return
  }

  lectureStore.setStatus(LECTURE_STATE.IDLE)
}

const finalizeQuestionFlow = async ({ qaItem, autoResume = false } = {}) => {
  if (qaItem) {
    qaItem.streaming = false
  }

  activeStreamingQaItemId = null
  qaStreamClient = null
  isAsking.value = false
  lectureStore.finishAnswer()

  if (autoResume && lectureStore.breakpointPage) {
    await handleResumeLecture()
  } else {
    restoreLectureStatusAfterAnswer()
  }

  scrollQAToBottom()
}

const fallbackAskQuestion = async ({ normalizedQuestion, qaItem, autoResume = false } = {}) => {
  const contextPageIndex = getQuestionContextPageIndex()
  const response = await askText({
    sessionId: lectureStore.sessionId,
    question: normalizedQuestion,
    pageIndex: contextPageIndex,
  })
  qaItem.answer = response.data?.answer || '当前没有获取到有效回答。'
  qaItem.evidence = Array.isArray(response.data?.evidence) ? response.data.evidence : []
  lectureStore.appendAnswerDelta(qaItem.answer || '')
  await finalizeQuestionFlow({ qaItem, autoResume })
}

const stopStreamingAnswer = async () => {
  qaStreamClient?.close()
  const qaItem = qaList.value.find(item => item.id === activeStreamingQaItemId)
  await finalizeQuestionFlow({ qaItem, autoResume: false })
}

const submitQuestion = async ({ inputQuestion = question.value.trim(), autoResume = false } = {}) => {
  const normalizedQuestion = String(inputQuestion || '').trim()
  if (!normalizedQuestion || isAsking.value || !lectureStore.sessionId) {
    return
  }

  const contextPageIndex = getQuestionContextPageIndex()

  isAsking.value = true
  lectureStore.enterAnswering(normalizedQuestion)
  clearError()
  const qaItem = {
    id: Date.now(),
    question: normalizedQuestion,
    answer: '',
    evidence: [],
    streaming: true,
  }

  qaList.value.push(qaItem)
  activeStreamingQaItemId = qaItem.id
  question.value = ''
  scrollQAToBottom()

  let hasSettled = false

  const settleWithFallback = async error => {
    if (hasSettled) {
      return
    }

    hasSettled = true
    qaStreamClient?.close()
    qaStreamClient = null
    showError(error, '流式回答失败，已降级为普通问答。')

    try {
      await fallbackAskQuestion({ normalizedQuestion, qaItem, autoResume })
    } catch (fallbackError) {
      const message = getErrorMessage(fallbackError, '提问失败，请稍后重试。')
      qaItem.answer = message
      lectureStore.appendAnswerDelta(message)
      showError(fallbackError, '提问失败，请稍后重试。')
      await finalizeQuestionFlow({ qaItem, autoResume: false })
    }
  }

  try {
    qaStreamClient = streamAskText(
      {
        sessionId: lectureStore.sessionId,
        question: normalizedQuestion,
        pageIndex: contextPageIndex,
      },
      {
        onMeta: payload => {
          if (hasSettled) {
            return
          }

          qaItem.evidence = Array.isArray(payload?.evidence) ? payload.evidence : []
          scrollQAToBottom()
        },
        onDelta: content => {
          if (hasSettled || !content) {
            return
          }

          qaItem.answer += content
          lectureStore.appendAnswerDelta(content)
          scrollQAToBottom()
        },
        onDone: () => {
          if (hasSettled) {
            return
          }

          hasSettled = true
          void finalizeQuestionFlow({ qaItem, autoResume })
        },
        onError: error => {
          if (hasSettled) {
            return
          }

          void settleWithFallback(error)
        },
      },
    )
    return true
  } catch (error) {
    await settleWithFallback(error)
    return false
  }
}

const scrollQAToBottom = () => {
  nextTick(() => {
    if (qaHistoryRef.value) {
      qaHistoryRef.value.scrollTop = qaHistoryRef.value.scrollHeight
    }
  })
}

const saveCourseCode = async () => {
  if (!canManageCourseCode.value || courseCodeLoading.value) {
    return
  }

  courseCodeLoading.value = true
  clearError()

  try {
    const response = await updateCoursewareCourseCode(coursewareId, normalizedCourseCodeInput.value)
    const nextCourseCode = response.data?.courseCode ?? normalizedCourseCodeInput.value
    savedCourseCode.value = normalizeCourseCodeInput(nextCourseCode)
    courseCodeInput.value = savedCourseCode.value
  } catch (error) {
    showError(error, '更新课程号失败，请稍后重试。')
  } finally {
    courseCodeLoading.value = false
  }
}

const clearCourseCode = async () => {
  if (!savedCourseCode.value && !normalizedCourseCodeInput.value) {
    return
  }

  courseCodeInput.value = ''
  await saveCourseCode()
}

watch(
  () => currentSlide.value?.id,
  () => {
    resetAudioProgress()
    resetPauseFlags()
    isSpeaking.value = false
    lectureStore.setAudioMode(useAudioPlayback.value ? 'audio' : 'speech')
  },
)

onMounted(async () => {
  authStore.restore()
  if (authStore.isStudent && routeCourseCode.value) {
    authStore.setActiveCourseCode(routeCourseCode.value)
  }
  canUseVoiceInterrupt.value = !isTeacherView.value && supportsVoiceInterrupt()
  updateVoiceInterruptState(
    canUseVoiceInterrupt.value ? VOICE_INTERRUPT_STATE.OFF : VOICE_INTERRUPT_STATE.UNAVAILABLE,
    canUseVoiceInterrupt.value
      ? '开启后会在检测到学生说话后自动打断课堂'
      : isTeacherView.value
        ? '教师预览模式已关闭语音打断。'
        : '当前浏览器不支持语音打断，请改用手动输入问题。',
  )

  playbackEngine = createLecturePlaybackEngine({
    getSlides: () => slides.value,
    getCurrentPage: () => currentPage.value,
    syncToPage,
    playCurrentPage: playCurrentSlideByPageIndex,
    stopPlayback: haltPlayback,
    setLectureStatus: status => lectureStore.setStatus(status),
    endedStatus: LECTURE_STATE.ENDED,
    onContinuousPlaybackChange: enabled => {
      isContinuousPlayback.value = enabled
    },
  })

  audioUnsubscribers.push(
    audioPlayer.onEnded(async () => {
      isSpeaking.value = false
      isAudioPaused.value = false
      audioCurrentTime.value = audioPlayer.getCurrentTime()
      await playbackEngine?.handlePlaybackEnded()
    }),
  )
  audioUnsubscribers.push(
    audioPlayer.onTimeUpdate(() => {
      audioCurrentTime.value = audioPlayer.getCurrentTime()
      audioDuration.value = audioPlayer.getDuration()
    }),
  )
  audioUnsubscribers.push(
    audioPlayer.onError(() => {
      if (playbackMode.value === 'audio' && isSpeaking.value && currentSlide.value?.content) {
        if (currentSlide.value.audioUrl) {
          failedAudioUrls.add(currentSlide.value.audioUrl)
        }
        showError('音频资源加载失败，已切换备用讲解链路。', '音频资源加载失败，已切换备用讲解链路。')
        fallbackToSpeech(currentSlide.value.content)
        return
      }

      isSpeaking.value = false
    }),
  )

  lectureStore.reset()
  lectureStore.setCoursewareId(coursewareId)
  if (isTeacherView.value) {
    await loadCoursewareMeta({ silent: true })
  }
  await fetchVideoRenderTask({ silent: true })
  const loaded = await loadSlides()
  if (loaded) {
    await startLectureSession()
  }
})

onUnmounted(() => {
  playbackEngine?.stopCurrentPage()
  clearVoiceRecognizerRestartTimer()
  speechRecognizer?.destroy?.()
  speechRecognizer = null
  qaStreamClient?.close()
  qaStreamClient = null
  stopVideoRenderPolling()
  disconnectLectureSocket()
  audioUnsubscribers.forEach(unsubscribe => unsubscribe())
  audioPlayer.destroy()
  lectureStore.reset()
})
</script>

<style scoped>
.lecture-page {
  position: relative;
  padding-bottom: 2rem;
}

.lecture-page::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 24rem;
  background:
    radial-gradient(circle at 10% 10%, rgba(14, 90, 224, 0.12), transparent 32%),
    radial-gradient(circle at 88% 0%, rgba(24, 126, 168, 0.14), transparent 28%);
  pointer-events: none;
}

.lecture-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.72fr) minmax(340px, 0.78fr);
  gap: 1.5rem;
  align-items: start;
}

.lecture-main,
.lecture-chat-panel {
  min-height: 42rem;
}

.lecture-main {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.lecture-video-stage {
  min-width: 0;
}

.lecture-control-card {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(244, 249, 255, 0.92)),
    radial-gradient(circle at top right, rgba(255, 140, 58, 0.08), transparent 28%);
}

.lecture-quiz-card {
  position: relative;
  overflow: hidden;
}

.control-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.control-label {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.control-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.voice-status-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.voice-status-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 1.9rem;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  background: rgba(126, 136, 166, 0.12);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.voice-status-pill--listening {
  background: rgba(95, 104, 255, 0.12);
  color: var(--primary-color);
}

.voice-status-pill--recording {
  background: rgba(31, 157, 103, 0.14);
  color: var(--success-color);
}

.voice-status-pill--completed {
  background: rgba(228, 156, 49, 0.14);
  color: var(--warning-color);
}

.voice-status-pill--unavailable {
  background: rgba(203, 65, 94, 0.14);
  color: var(--error-color);
}

.voice-status-hint {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}

.voice-volume-meter {
  position: relative;
  width: 100%;
  height: 0.55rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(126, 136, 166, 0.12);
}

.voice-volume-meter.active {
  background: rgba(95, 104, 255, 0.12);
}

.voice-volume-bar {
  display: block;
  width: 100%;
  height: 100%;
  transform-origin: left center;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
}

.lecture-chat-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 6.25rem;
  min-height: calc(100vh - 7.5rem);
  max-height: calc(100vh - 7.5rem);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(247, 250, 255, 0.8)),
    radial-gradient(circle at top right, rgba(14, 90, 224, 0.08), transparent 26%);
  backdrop-filter: blur(16px);
}

.teacher-panel {
  justify-content: flex-start;
  min-height: auto;
  max-height: none;
}

.teacher-panel__header {
  align-items: center;
}

.teacher-panel__intro,
.teacher-panel__hint {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

.teacher-course-code-status {
  font-weight: 700;
  white-space: normal;
  text-align: right;
}

.teacher-course-code-form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(104, 130, 171, 0.12);
}

.teacher-course-code-label {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.teacher-course-code-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.chat-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.chat-header h2 {
  margin: 0;
  font-size: 1.45rem;
}

.chat-header__status {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.chat-history {
  flex: 1;
  min-height: 18rem;
  max-height: none;
  overflow-y: auto;
  padding-right: 0.35rem;
  padding-bottom: 0.35rem;
}

.chat-empty {
  display: grid;
  place-items: center;
  min-height: 100%;
  text-align: center;
  color: var(--text-secondary);
}

.chat-empty h3 {
  margin: 0;
  color: var(--text-primary);
}

.chat-empty p {
  margin: 0.7rem 0 0;
  line-height: 1.8;
}

.chat-turn {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  margin-bottom: 1rem;
}

.bubble {
  max-width: 100%;
  padding: 1rem 1.1rem;
  border-radius: 1.2rem;
  box-shadow: var(--shadow-sm);
}

.bubble--user {
  align-self: flex-end;
  max-width: 84%;
  border-top-right-radius: 0.5rem;
  background: linear-gradient(135deg, rgba(14, 90, 224, 0.96), rgba(24, 126, 168, 0.92));
  color: #ffffff;
}

.bubble--assistant {
  align-self: flex-start;
  max-width: 92%;
  border-top-left-radius: 0.5rem;
  background:
    linear-gradient(180deg, rgba(250, 252, 255, 0.96), rgba(244, 249, 255, 0.94)),
    radial-gradient(circle at top right, rgba(24, 126, 168, 0.06), transparent 30%);
  border: 1px solid rgba(104, 130, 171, 0.12);
}

.bubble-role {
  display: inline-block;
  margin-bottom: 0.55rem;
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.bubble p {
  margin: 0;
  line-height: 1.8;
}

.bubble-answer {
  color: var(--text-secondary);
  line-height: 1.8;
}

.bubble-streaming {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.7rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.bubble-streaming__dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  background: var(--primary-color);
  box-shadow: 0 0 0 0 rgba(95, 104, 255, 0.35);
  animation: pulse-dot 1.6s ease-out infinite;
}

.bubble-answer :deep(p) {
  margin: 0.45rem 0;
}

.bubble-answer :deep(code) {
  padding: 0.1rem 0.35rem;
  border-radius: 0.35rem;
  background: rgba(95, 104, 255, 0.08);
}

.bubble-answer :deep(pre) {
  margin: 0.65rem 0;
  padding: 0.9rem;
  border-radius: var(--radius-md);
  background: rgba(238, 242, 255, 0.78);
  overflow-x: auto;
}

.evidence-panel {
  margin-top: 0.8rem;
}

.evidence-panel summary {
  cursor: pointer;
  color: var(--primary-color);
  font-weight: 600;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.evidence-item {
  padding: 0.85rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(127, 138, 177, 0.12);
}

.evidence-item__meta {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.45rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.evidence-item p {
  color: var(--text-secondary);
}

.chat-composer {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  padding: 0.85rem;
  border-radius: calc(var(--radius-lg) - 0.1rem);
  background: rgba(246, 249, 255, 0.94);
  border: 1px solid rgba(104, 130, 171, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
}

.chat-composer > .app-input {
  flex: 1;
}

@keyframes pulse-dot {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(95, 104, 255, 0.3);
  }

  70% {
    transform: scale(1);
    box-shadow: 0 0 0 0.42rem rgba(95, 104, 255, 0);
  }

  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(95, 104, 255, 0);
  }
}

.toast {
  position: fixed;
  right: 1.25rem;
  bottom: 1.25rem;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 1rem;
  max-width: min(26rem, calc(100vw - 2rem));
  padding: 0.95rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(203, 65, 94, 0.97);
  color: #ffffff;
  box-shadow: var(--shadow-md);
}

.toast button {
  color: inherit;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 1180px) {
  .lecture-layout {
    grid-template-columns: 1fr;
  }

  .lecture-chat-panel {
    min-height: auto;
    max-height: none;
    position: static;
  }
}

@media (max-width: 768px) {
  .control-grid {
    grid-template-columns: 1fr;
  }

  .chat-composer {
    flex-direction: column;
    align-items: stretch;
  }

  .teacher-course-code-actions {
    flex-direction: column;
  }

  .bubble--user,
  .bubble--assistant {
    max-width: 100%;
  }
}

@media (max-width: 640px) {
  .toast {
    left: 1rem;
    right: 1rem;
    max-width: none;
  }
}
</style>
