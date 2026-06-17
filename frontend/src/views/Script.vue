<template>
  <div class="script-page">
    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">Script Review</span>
          <h1 class="page-title">课件讲稿</h1>
          <p class="page-description">
            逐页检查课件页面、讲稿、音频和数字人设置，确认后再进入课堂或生成讲解视频。
          </p>
        </div>

        <div class="header-actions">
          <AppButton variant="secondary" @click="goBack">返回资源详情</AppButton>

          <AppButton
            v-if="!scriptData && scriptStatus !== 'GENERATING_SCRIPT' && canModifyScript"
            @click="handleGenerateScript"
          >
            生成讲稿
          </AppButton>

          <template v-else-if="scriptData">
            <AppButton
              v-if="!isEditing && canModifyScript"
              variant="secondary"
              @click="beginEdit"
            >
              编辑讲稿
            </AppButton>
            <AppButton
              v-if="isEditing && canModifyScript"
              variant="secondary"
              :disabled="saving"
              @click="cancelEdit"
            >
              取消编辑
            </AppButton>
            <AppButton
              v-if="isEditing && canModifyScript"
              :disabled="saving || !isDirty"
              @click="handleSaveScript"
            >
              {{ saving ? '保存中...' : '保存讲稿设置' }}
            </AppButton>
            <AppButton
              v-if="!isEditing && missingAudioCount > 0 && canModifyScript"
              variant="secondary"
              :disabled="scriptStatus === 'GENERATING_SCRIPT'"
              @click="handleBackfillAudio"
            >
              补齐缺失音频
            </AppButton>
            <AppButton
              v-if="!isEditing"
              :disabled="scriptStatus === 'GENERATING_SCRIPT'"
              @click="startLecturePage"
            >
              进入课堂
            </AppButton>
          </template>

          <AppButton
            v-if="canModifyScript"
            variant="secondary"
            :disabled="!scriptData || isEditing || videoRenderTask?.status === 'RENDERING'"
            @click="handleRenderVideo"
          >
            {{ renderVideoButtonText }}
          </AppButton>
        </div>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="script-layout">
        <AppCard class="script-outline-card" tone="glass">
          <div class="outline-header">
            <div>
              <p class="outline-label">Script Map</p>
              <h2>{{ scriptData?.coursewareId || coursewareId }}</h2>
            </div>
            <StatusBadge :label="statusMeta.text" :tone="statusMeta.tone" />
          </div>

          <div v-if="missingAudioCount > 0 && canModifyScript" class="outline-tip">
            还有 {{ missingAudioCount }} 页缺少音频，建议先补齐再渲染视频。
          </div>

          <div v-if="scriptData?.outline?.length" class="outline-list">
            <button
              v-for="(item, index) in scriptData.outline"
              :key="item.id"
              class="outline-item"
              :class="{ active: activeSegmentId === item.id }"
              @click="scrollToSegment(item.id)"
            >
              <span>{{ index + 1 }}</span>
              <strong>{{ item.title }}</strong>
            </button>
          </div>
          <div v-else class="outline-empty">
            讲稿生成后，这里会显示逐页目录并支持定位到右侧对应讲稿。
          </div>
        </AppCard>

        <div class="script-main">
          <div v-if="loading" class="surface-panel state-card">正在加载讲稿...</div>

          <AppCard v-else-if="scriptStatus === 'GENERATING_SCRIPT'" class="state-card" tone="glass">
            <div class="generating-state">
              <span class="spinner"></span>
              <div>
                <h3>讲稿生成中</h3>
                <p>系统正在整理逐页讲解和音频，请稍候。</p>
              </div>
            </div>
          </AppCard>

          <template v-else-if="scriptData">
            <AppCard v-if="scriptData.opening" class="intro-card" tone="subtle">
              <div class="intro-card__header">
                <span class="pill">Opening</span>
                <span class="intro-note">当前开场白仍使用自动生成版本</span>
              </div>
              <p>{{ scriptData.opening }}</p>
            </AppCard>

            <AppCard v-if="isEditing && canModifyScript" class="editor-tip-card" tone="glass">
              <h3>编辑提示</h3>
              <p>
                每张课件页面会显示在对应讲稿上方。你可以一边看页面，一边改讲稿，也可以勾选哪些页需要做成数字人片段。
                连续勾选的页面会自动合并成一次 `videoretalk` 生成任务。
              </p>
            </AppCard>

            <div class="segment-list">
              <AppCard
                v-for="segment in visibleSegments"
                :key="segment.id"
                :id="segmentAnchorId(segment.id)"
                :data-segment-id="segment.id"
                class="segment-card"
                :class="{ active: activeSegmentId === segment.id }"
                tone="glass"
              >
                <figure v-if="segment.pageImageUrl || segment.pageImagePath" class="segment-preview">
                  <img
                    :src="segment.pageImageUrl || segment.pageImagePath"
                    :alt="`${segment.title} 课件页`"
                  />
                  <figcaption>第 {{ segment.pageIndex }} 页课件</figcaption>
                </figure>

                <div class="segment-card__header">
                  <div class="segment-title-block">
                    <span class="pill">第 {{ segment.pageIndex }} 页</span>
                    <template v-if="isEditing">
                      <input
                        v-model.trim="segment.title"
                        class="segment-title-input"
                        type="text"
                        :placeholder="`第 ${segment.pageIndex} 页标题`"
                      />
                    </template>
                    <h3 v-else>{{ segment.title }}</h3>
                  </div>

                  <div class="segment-side">
                    <StatusBadge
                      :label="segment.audioUrl ? '音频已就绪' : '待补音频'"
                      :tone="segment.audioUrl ? 'success' : 'warning'"
                    />

                    <label v-if="isEditing" class="digital-human-toggle">
                      <input v-model="segment.digitalHumanEnabled" type="checkbox" />
                      <span>数字人片段</span>
                    </label>
                    <span
                      v-else-if="segment.digitalHumanEnabled"
                      class="digital-human-badge"
                    >
                      数字人
                    </span>
                  </div>
                </div>

                <div class="segment-card__content">
                  <textarea
                    v-if="isEditing"
                    v-model="segment.content"
                    class="segment-textarea"
                    rows="8"
                  />
                  <p v-else>{{ segment.content }}</p>
                </div>

                <div class="segment-footer">
                  <div v-if="segment.knowledgePoints?.length" class="tag-list">
                    <span v-for="point in segment.knowledgePoints" :key="point" class="tag-chip">
                      {{ point }}
                    </span>
                  </div>
                  <p v-if="segment.digitalHumanEnabled" class="segment-hint">
                    连续勾选的页面会自动合并为一段数字人视频，仍然使用当前页对应的原始 TTS 音频。
                  </p>
                </div>
              </AppCard>
            </div>

            <AppCard v-if="scriptData.closing" class="intro-card" tone="subtle">
              <div class="intro-card__header">
                <span class="pill">Closing</span>
                <span class="intro-note">当前结尾仍使用自动生成版本</span>
              </div>
              <p>{{ scriptData.closing }}</p>
            </AppCard>

            <AppCard v-if="videoRenderTask" class="video-render-card" tone="glass">
              <div class="video-render-card__header">
                <div>
                  <span class="pill">Lecture Video</span>
                  <h3>课件讲解视频</h3>
                  <p>{{ resolvedVideoRenderStatusText }}</p>
                </div>
                <StatusBadge
                  :label="videoRenderTask.status || 'PENDING'"
                  :tone="videoRenderTask.status === 'READY' ? 'success' : videoRenderTask.status === 'FAILED' ? 'danger' : 'warning'"
                />
              </div>

              <div v-if="videoRenderTask.status === 'READY' && videoRenderTask.hlsUrl" class="video-render-player">
                <div v-if="canModifyScript" class="inline-alert inline-alert--info">
                  如果你修改了讲稿或数字人勾选，请重新生成讲解视频，让字幕、音频和数字人片段保持同步。
                </div>
                <HlsVideoPlayer
                  :src="resolvedVideoRenderUrl"
                  title="课件讲解视频"
                  @error="message => (videoPlayerError = message)"
                  @ready="videoPlayerError = ''"
                />
                <div v-if="videoPlayerError" class="inline-alert inline-alert--danger">
                  {{ videoPlayerError }}
                </div>
              </div>

              <div v-else-if="videoRenderTask.status === 'FAILED'" class="inline-alert inline-alert--danger">
                {{ videoRenderTask.errorMessage || '视频生成失败，请检查页面图、音频或 Python 日志。' }}
              </div>
            </AppCard>
          </template>

          <AppCard v-else tone="glass">
            <EmptyState
              title="暂时还没有讲稿"
              :description="canModifyScript
                ? '系统会基于解析结果生成可检查、可修改的逐页讲稿。'
                : '这份共享课件的讲稿尚未准备完成，请稍后再进入查看。'"
              :action-label="canModifyScript ? '生成讲稿' : undefined"
              @action="canModifyScript && handleGenerateScript()"
            />
          </AppCard>
        </div>
      </div>
    </section>

    <div v-if="errorMsg" class="toast" @click="errorMsg = ''">
      <span>{{ errorMsg }}</span>
      <button type="button">关闭</button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import HlsVideoPlayer from '@/components/video/HlsVideoPlayer.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  generateScript,
  getCoursewareDetail,
  getCoursewareScript,
  getCoursewareVideoRenderTask,
  renderCoursewareVideo,
  updateCoursewareScript,
} from '@/api/courseware'
import { getCoursewareStatusMeta } from '@/constants/courseware'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(true)
const scriptData = ref(null)
const coursewareDetail = ref(null)
const scriptStatus = ref('')
const activeSegmentId = ref('')
const errorMsg = ref('')
const videoRenderTask = ref(null)
const videoPlayerError = ref('')
const isEditing = ref(false)
const saving = ref(false)
const editableSegments = ref([])

let pollTimer = null
let videoRenderPollTimer = null
let segmentObserver = null

const coursewareId = route.params.coursewareId
const routeCourseCode = computed(() => String(route.query.courseCode || '').trim().toUpperCase())
const accessMode = computed(() => String(coursewareDetail.value?.accessMode || 'OWNED').trim().toUpperCase())
const canModifyScript = computed(() => accessMode.value !== 'SHARED')

const statusMeta = computed(() => {
  if (scriptStatus.value === 'GENERATING_SCRIPT') {
    return getCoursewareStatusMeta('GENERATING_SCRIPT')
  }
  return getCoursewareStatusMeta(scriptStatus.value || 'READY')
})

const visibleSegments = computed(() => (isEditing.value ? editableSegments.value : scriptData.value?.segments || []))

const missingAudioCount = computed(() => {
  const segments = scriptData.value?.segments || []
  return segments.filter(segment => !segment.audioUrl).length
})

const isDirty = computed(() => {
  if (!isEditing.value || !scriptData.value) {
    return false
  }
  const originalSegments = scriptData.value.segments || []
  if (originalSegments.length !== editableSegments.value.length) {
    return true
  }
  return editableSegments.value.some((segment, index) => {
    const original = originalSegments[index]
    return (
      segment.title !== original.title ||
      segment.content !== original.content ||
      Boolean(segment.digitalHumanEnabled) !== Boolean(original.digitalHumanEnabled)
    )
  })
})

const renderVideoButtonText = computed(() => {
  if (videoRenderTask.value?.status === 'RENDERING') {
    return `视频生成中 ${videoRenderTask.value.progress || 0}%`
  }
  if (videoRenderTask.value?.status === 'READY') {
    return '重新生成讲解视频'
  }
  return '生成讲解视频'
})

const videoRenderStatusText = computed(() => {
  const task = videoRenderTask.value
  if (!task) {
    return ''
  }
  if (task.status === 'READY') {
    const seconds = task.durationMs ? Math.round(task.durationMs / 1000) : 0
    return `已生成 ${task.segmentCount || 0} 个片段，总时长约 ${seconds} 秒，可直接预览。`
  }
  if (task.status === 'FAILED') {
    return '视频生成失败，请根据错误信息排查。'
  }
  return task.message || '正在整理页面图、字幕和音频。'
})

const segmentAnchorId = segmentId => `segment-${segmentId}`

const resolvedVideoRenderStatusText = computed(() => {
  const task = videoRenderTask.value
  if (!task) {
    return ''
  }

  if (String(task.status || '').toUpperCase() === 'READY') {
    const seconds = task.durationMs ? Math.round(task.durationMs / 1000) : 0
    const base = `已生成 ${task.segmentCount || 0} 个片段，总时长约 ${seconds} 秒，可直接预览。`
    if (task.message && task.message !== 'Courseware lecture video rendered') {
      return `${base} ${task.message}`
    }
    return base
  }

  if (String(task.status || '').toUpperCase() === 'FAILED') {
    return task.errorMessage || '视频生成失败，请根据错误信息排查。'
  }

  return task.message || '正在整理页面图、字幕和音频。'
})

const appendCacheKey = (url, cacheKey) => {
  const rawUrl = String(url || '').trim()
  if (!rawUrl) {
    return ''
  }

  const normalizedKey = Number(cacheKey)
  if (!Number.isFinite(normalizedKey) || normalizedKey <= 0) {
    return rawUrl
  }

  return `${rawUrl}${rawUrl.includes('?') ? '&' : '?'}v=${normalizedKey}`
}

const resolvedVideoRenderUrl = computed(() =>
  appendCacheKey(videoRenderTask.value?.hlsUrl, videoRenderTask.value?.cacheKey),
)

const normalizeScript = raw => {
  const segments = Array.isArray(raw?.segments)
    ? raw.segments.map((segment, index) => ({
        id: segment?.id || segment?.nodeId || `segment-${index + 1}`,
        nodeId: segment?.nodeId || segment?.id || `node-${index + 1}`,
        pageIndex: Number(segment?.pageIndex || index + 1),
        title: segment?.title || `第 ${index + 1} 页`,
        content: segment?.content || '',
        knowledgePoints: Array.isArray(segment?.knowledgePoints) ? segment.knowledgePoints : [],
        audioUrl: segment?.audioUrl || null,
        pageImagePath: segment?.pageImagePath || null,
        pageImageUrl: segment?.pageImageUrl || segment?.pageImagePath || null,
        visualSummary: segment?.visualSummary || '',
        visualObjects: Array.isArray(segment?.visualObjects) ? segment.visualObjects : [],
        digitalHumanEnabled: Boolean(segment?.digitalHumanEnabled),
      }))
    : []

  const outline = Array.isArray(raw?.outline) && raw.outline.length
    ? raw.outline.map((item, index) => ({
        id: item?.id || segments[index]?.id || `outline-${index + 1}`,
        title: item?.title || segments[index]?.title || `第 ${index + 1} 页`,
      }))
    : segments.map(segment => ({
        id: segment.id,
        title: segment.title,
      }))

  return {
    coursewareId: raw?.coursewareId || coursewareId,
    opening: raw?.opening || '',
    closing: raw?.closing || '',
    status: raw?.status || 'READY',
    outline,
    segments,
  }
}

const cloneSegments = segments =>
  segments.map(segment => ({
    ...segment,
    knowledgePoints: [...(segment.knowledgePoints || [])],
    visualObjects: [...(segment.visualObjects || [])],
  }))

const teardownSegmentObserver = () => {
  if (segmentObserver) {
    segmentObserver.disconnect()
    segmentObserver = null
  }
}

const setupSegmentObserver = async () => {
  teardownSegmentObserver()
  await nextTick()

  const elements = Array.from(document.querySelectorAll('[data-segment-id]'))
  if (!elements.length || typeof IntersectionObserver === 'undefined') {
    return
  }

  segmentObserver = new IntersectionObserver(
    entries => {
      const visibleEntry = entries
        .filter(entry => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0]

      if (visibleEntry?.target?.dataset?.segmentId) {
        activeSegmentId.value = visibleEntry.target.dataset.segmentId
      }
    },
    {
      rootMargin: '-18% 0px -55% 0px',
      threshold: [0.2, 0.4, 0.7],
    },
  )

  elements.forEach(element => segmentObserver.observe(element))
}

const applyScriptData = raw => {
  const normalized = raw ? normalizeScript(raw) : null
  scriptData.value = normalized
  scriptStatus.value = normalized?.status || raw?.status || ''
  activeSegmentId.value = normalized?.segments?.[0]?.id || normalized?.outline?.[0]?.id || ''
  editableSegments.value = normalized?.segments ? cloneSegments(normalized.segments) : []
  setupSegmentObserver()
}

const showError = (error, fallback) => {
  errorMsg.value = getErrorMessage(error, fallback)
}

const loadCoursewareDetail = async () => {
  try {
    const response = await getCoursewareDetail(coursewareId)
    coursewareDetail.value = response.data || null
  } catch {
    coursewareDetail.value = null
  }
}

const fetchScript = async () => {
  loading.value = true
  try {
    const response = await getCoursewareScript(coursewareId)
    applyScriptData(response.data)
  } catch (error) {
    scriptData.value = null
    showError(error, '无法获取讲稿，请稍后重试。')
  } finally {
    loading.value = false
  }
}

const handleGenerateScript = async () => {
  if (!canModifyScript.value) {
    return
  }
  scriptStatus.value = 'GENERATING_SCRIPT'
  errorMsg.value = ''

  try {
    await generateScript(coursewareId)
    pollGenerateStatus()
  } catch (error) {
    scriptStatus.value = ''
    showError(error, '生成讲稿失败，请稍后重试。')
  }
}

const handleBackfillAudio = async () => {
  if (!canModifyScript.value) {
    return
  }
  errorMsg.value = ''
  try {
    await generateScript(coursewareId)
    scriptStatus.value = 'GENERATING_SCRIPT'
    pollGenerateStatus()
  } catch (error) {
    showError(error, '补齐音频失败，请稍后重试。')
  }
}

const pollGenerateStatus = () => {
  let attempts = 0
  const maxAttempts = 60

  if (pollTimer) {
    clearInterval(pollTimer)
  }

  pollTimer = setInterval(async () => {
    attempts += 1
    if (attempts > maxAttempts) {
      clearInterval(pollTimer)
      pollTimer = null
      scriptStatus.value = ''
      errorMsg.value = '讲稿生成超时，请稍后重试。'
      return
    }

    try {
      const response = await getCoursewareScript(coursewareId)
      const raw = response.data
      const normalized = raw ? normalizeScript(raw) : null
      if (normalized?.segments?.length) {
        clearInterval(pollTimer)
        pollTimer = null
        applyScriptData(raw)
      }
    } catch {
      // Ignore transient polling errors.
    }
  }, 3000)
}

const beginEdit = () => {
  editableSegments.value = cloneSegments(scriptData.value?.segments || [])
  isEditing.value = true
  setupSegmentObserver()
}

const cancelEdit = () => {
  editableSegments.value = cloneSegments(scriptData.value?.segments || [])
  isEditing.value = false
  setupSegmentObserver()
}

const handleSaveScript = async () => {
  if (!scriptData.value || !canModifyScript.value) {
    return
  }
  saving.value = true
  errorMsg.value = ''

  try {
    const response = await updateCoursewareScript(coursewareId, {
      regenerateAudio: true,
      segments: editableSegments.value.map(segment => ({
        id: segment.id,
        title: segment.title,
        content: segment.content,
        digitalHumanEnabled: Boolean(segment.digitalHumanEnabled),
      })),
    })
    applyScriptData(response.data)
    isEditing.value = false
  } catch (error) {
    showError(error, '保存讲稿失败，请稍后重试。')
  } finally {
    saving.value = false
  }
}

const scrollToSegment = async segmentId => {
  activeSegmentId.value = segmentId
  await nextTick()
  const element = document.getElementById(segmentAnchorId(segmentId))
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const startLecturePage = () => {
  router.push(buildSharedRouteLocation('Lecture'))
}

const goBack = () => {
  router.push(buildSharedRouteLocation('ResourceDetail'))
}

const buildSharedRouteLocation = name => ({
  name,
  params: { coursewareId },
  query: routeCourseCode.value ? { courseCode: routeCourseCode.value } : undefined,
})

const fetchVideoRenderTask = async ({ silent = false } = {}) => {
  try {
    const response = await getCoursewareVideoRenderTask(coursewareId)
    videoRenderTask.value = response.data || null
    return videoRenderTask.value
  } catch (error) {
    if (!silent) {
      showError(error, '无法获取视频生成状态，请稍后重试。')
    }
    return null
  }
}

const handleRenderVideo = async () => {
  if (!scriptData.value || !canModifyScript.value) {
    return
  }

  videoPlayerError.value = ''
  errorMsg.value = ''

  try {
    const response = await renderCoursewareVideo(coursewareId)
    videoRenderTask.value = response.data || null
    pollVideoRenderStatus()
  } catch (error) {
    showError(error, '触发讲解视频生成失败，请确认讲稿和页面图已准备完成。')
  }
}

const pollVideoRenderStatus = () => {
  if (videoRenderPollTimer) {
    clearInterval(videoRenderPollTimer)
  }

  let attempts = 0
  videoRenderPollTimer = setInterval(async () => {
    attempts += 1
    const task = await fetchVideoRenderTask({ silent: true })
    if (!task || task.status === 'READY' || task.status === 'FAILED' || attempts > 120) {
      clearInterval(videoRenderPollTimer)
      videoRenderPollTimer = null
    }
  }, 3000)
}

onMounted(() => {
  authStore.restore()
  if (authStore.isStudent && routeCourseCode.value) {
    authStore.setActiveCourseCode(routeCourseCode.value)
  }
  loadCoursewareDetail()
  fetchScript()
  fetchVideoRenderTask({ silent: true })
})

onUnmounted(() => {
  teardownSegmentObserver()
  if (pollTimer) {
    clearInterval(pollTimer)
  }
  if (videoRenderPollTimer) {
    clearInterval(videoRenderPollTimer)
  }
})
</script>

<style scoped>
.script-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 1.25rem;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.script-outline-card {
  position: sticky;
  top: 6rem;
  height: fit-content;
}

.outline-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.outline-label {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.outline-header h2 {
  margin: 0.4rem 0 0;
  font-size: 1.15rem;
  word-break: break-all;
}

.outline-tip {
  margin-top: 1rem;
  padding: 0.85rem 0.95rem;
  border-radius: var(--radius-md);
  background: rgba(255, 186, 56, 0.12);
  border: 1px solid rgba(255, 186, 56, 0.18);
  color: #8b5e00;
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

.outline-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-top: 1.2rem;
}

.outline-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.8rem 0.9rem;
  border-radius: var(--radius-md);
  border: 1px solid rgba(132, 143, 184, 0.12);
  background: rgba(248, 250, 255, 0.86);
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    transform var(--transition-base);
}

.outline-item:hover,
.outline-item.active {
  transform: translateY(-1px);
  border-color: rgba(14, 90, 224, 0.22);
  background: rgba(14, 90, 224, 0.08);
}

.outline-item span {
  width: 1.75rem;
  height: 1.75rem;
  display: grid;
  place-items: center;
  border-radius: 0.75rem;
  background: rgba(14, 90, 224, 0.12);
  color: var(--primary-color);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.outline-item strong {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}

.outline-empty,
.state-card {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 14rem;
  color: var(--text-secondary);
  text-align: center;
}

.script-main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.intro-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.intro-note {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.intro-card p,
.editor-tip-card p {
  margin: 0.9rem 0 0;
  color: var(--text-secondary);
  line-height: 1.9;
  white-space: pre-wrap;
}

.editor-tip-card h3 {
  margin: 0;
}

.segment-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.segment-card {
  scroll-margin-top: 7rem;
}

.segment-card.active {
  border-color: rgba(14, 90, 224, 0.24);
  box-shadow: 0 20px 44px rgba(14, 90, 224, 0.12);
}

.segment-preview {
  margin: 0 0 1rem;
}

.segment-preview img {
  width: 100%;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(132, 143, 184, 0.16);
  background: rgba(242, 246, 255, 0.72);
  display: block;
}

.segment-preview figcaption {
  margin-top: 0.6rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.04em;
}

.segment-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.segment-title-block {
  width: 100%;
}

.segment-card__header h3 {
  margin: 0.8rem 0 0;
  font-size: 1.35rem;
}

.segment-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.75rem;
}

.segment-title-input,
.segment-textarea {
  width: 100%;
  border: 1px solid rgba(132, 143, 184, 0.24);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.96);
  color: var(--text-primary);
  box-shadow: inset 0 1px 2px rgba(14, 24, 44, 0.04);
  transition:
    border-color var(--transition-base),
    box-shadow var(--transition-base);
}

.segment-title-input {
  margin-top: 0.8rem;
  min-height: 2.8rem;
  padding: 0 0.95rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.segment-textarea {
  min-height: 12rem;
  padding: 0.95rem 1rem;
  line-height: 1.9;
  resize: vertical;
}

.segment-title-input:focus,
.segment-textarea:focus {
  outline: none;
  border-color: rgba(14, 90, 224, 0.36);
  box-shadow: 0 0 0 4px rgba(14, 90, 224, 0.1);
}

.segment-card__content p {
  margin: 1rem 0 0;
  color: var(--text-secondary);
  line-height: 1.95;
  white-space: pre-wrap;
}

.segment-footer {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.digital-human-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(14, 90, 224, 0.16);
  background: rgba(14, 90, 224, 0.08);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.digital-human-toggle input {
  margin: 0;
}

.digital-human-badge {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.38rem 0.8rem;
  border-radius: 999px;
  background: rgba(34, 181, 115, 0.12);
  color: #13814f;
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.segment-hint {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.7;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 1rem;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.4rem 0.8rem;
  border-radius: 999px;
  background: rgba(14, 90, 224, 0.08);
  color: var(--primary-color);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.video-render-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.video-render-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.video-render-card__header h3 {
  margin: 0.65rem 0 0;
  font-size: 1.25rem;
}

.video-render-card__header p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.video-render-player {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.inline-alert {
  padding: 0.85rem 1rem;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

.inline-alert--info {
  color: #3e507c;
  background: rgba(14, 90, 224, 0.08);
  border: 1px solid rgba(14, 90, 224, 0.14);
}

.inline-alert--danger {
  color: #b53f58;
  background: rgba(240, 74, 110, 0.1);
  border: 1px solid rgba(240, 74, 110, 0.14);
}

.generating-state {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.spinner {
  width: 1.2rem;
  height: 1.2rem;
  border-radius: 999px;
  border: 2px solid rgba(14, 90, 224, 0.16);
  border-top-color: var(--primary-color);
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1024px) {
  .script-layout {
    grid-template-columns: 1fr;
  }

  .script-outline-card {
    position: static;
  }

  .segment-card__header,
  .video-render-card__header,
  .intro-card__header {
    flex-direction: column;
  }

  .segment-side {
    align-items: flex-start;
  }
}
</style>
