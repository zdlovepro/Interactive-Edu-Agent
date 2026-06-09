<template>
  <div class="upload-page">
    <section class="page-shell page-section upload-hero">
      <div>
        <span class="eyebrow">本地上传</span>
        <h1 class="page-title">上传本地课件</h1>
        <p class="page-description">
          这里只处理本地 PDF/PPT/PPTX 上传。普通 URL 导入和超星导入请从导入中心进入，避免流程混在一起。
        </p>
      </div>
      <AppButton variant="secondary" @click="router.push('/imports')">返回导入中心</AppButton>
    </section>

    <section class="page-shell upload-layout">
      <AppCard class="upload-main-card" tone="accent">
        <FileUpload
          :disabled="uploadStatus?.status === 'uploading'"
          @file-selected="handleFileSelected"
          @error="handleError"
        />

        <div class="upload-status-panel">
          <div class="status-summary">
            <div>
              <p class="status-label">当前状态</p>
              <h3>{{ currentStatusTitle }}</h3>
              <p class="status-text">{{ currentStatusMessage }}</p>
            </div>
            <StatusBadge :label="currentStatusBadge.text" :tone="currentStatusBadge.tone" />
          </div>

          <div v-if="showProgress" class="progress-track">
            <div class="progress-fill" :style="{ width: `${uploadStatus.progress || 0}%` }"></div>
          </div>

          <div v-if="latestCourseware" class="next-actions">
            <AppButton variant="secondary" size="sm" @click="openDetail(latestCourseware)">
              查看资源详情
            </AppButton>
            <AppButton
              size="sm"
              :disabled="latestCourseware.status !== 'READY'"
              @click="enterLecture(latestCourseware)"
            >
              进入课堂
            </AppButton>
          </div>
        </div>
      </AppCard>

      <div class="upload-side-column">
        <AppCard tone="glass" class="side-card">
          <h3>上传流程</h3>
          <ol class="flow-list">
            <li>上传本地课件文件</li>
            <li>后端解析页面与文本结构</li>
            <li>进入资源详情页查看下一步</li>
            <li>生成讲稿后进入互动课堂</li>
          </ol>
        </AppCard>

        <AppCard tone="subtle" class="side-card">
          <h3>其他导入方式</h3>
          <p>如果你要从超星课程页或普通 URL 导入，请使用导入中心的独立入口。</p>
          <AppButton variant="secondary" size="sm" @click="router.push('/imports')">
            打开导入中心
          </AppButton>
        </AppCard>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">最近课件</span>
          <h2 class="page-title section-title">最近上传和处理的课件资源</h2>
        </div>
      </div>

      <div v-if="uploadError" class="inline-error">
        <span>{{ uploadError }}</span>
        <div class="inline-error__actions">
          <button v-if="canRetryUpload" type="button" @click="retryLastUpload">重新上传</button>
          <button type="button" @click="uploadError = null">关闭</button>
        </div>
      </div>

      <div v-if="uploadedCourseware.length" class="grid-auto">
        <CoursewareCard
          v-for="item in uploadedCourseware"
          :key="item.id"
          :courseware="item"
          @view-detail="openDetail"
          @view-script="openScript"
          @enter-lecture="enterLecture"
          @retry="openDetail"
        />
      </div>

      <AppCard v-else tone="glass">
        <EmptyState
          title="还没有上传记录"
          description="上传一个课件后，这里会显示最近的课件资源与解析进度。"
        />
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import FileUpload from '@/components/Upload/FileUpload.vue'
import CoursewareCard from '@/components/course/CoursewareCard.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { getCoursewareDetail, listCourseware, uploadCourseware } from '@/api/courseware'
import { getCoursewareStatusMeta } from '@/constants/courseware'
import { getErrorMessage } from '@/utils'

const router = useRouter()

const uploadStatus = ref(null)
const uploadError = ref(null)
const uploadedCourseware = ref([])
const latestCoursewareId = ref('')
const lastSelectedFile = ref(null)

let pollTimer = null

const latestCourseware = computed(() =>
  uploadedCourseware.value.find(item => item.id === latestCoursewareId.value) || uploadedCourseware.value[0] || null,
)

const currentStatusTitle = computed(() => {
  if (!uploadStatus.value) {
    return '未选择文件'
  }
  if (uploadStatus.value.status === 'uploading') {
    return '上传中'
  }
  if (uploadStatus.value.status === 'success') {
    return '处理中'
  }
  return '上传失败'
})

const currentStatusMessage = computed(() => {
  return uploadStatus.value?.message || '选择一个课件后，系统会在这里展示上传与解析进度。'
})

const currentStatusBadge = computed(() => {
  if (!uploadStatus.value) {
    return { text: '未开始', tone: 'neutral' }
  }
  if (uploadStatus.value.status === 'uploading') {
    return { text: '上传中', tone: 'accent' }
  }
  if (uploadStatus.value.status === 'success') {
    return { text: '处理中', tone: 'success' }
  }
  return { text: '失败', tone: 'danger' }
})

const showProgress = computed(() => uploadStatus.value && uploadStatus.value.progress !== undefined)
const canRetryUpload = computed(
  () => Boolean(lastSelectedFile.value) && uploadStatus.value?.status !== 'uploading',
)

function normalizeCoursewareItem(item) {
  return {
    id: item?.id || item?.coursewareId || '',
    name: item?.name || '未命名课件',
    status: String(item?.status || 'UPLOADED').trim().toUpperCase(),
    createdAt: item?.createdAt || item?.updatedAt || new Date().toISOString(),
    updatedAt: item?.updatedAt || item?.createdAt || '',
    currentTaskStatus: item?.currentTaskStatus || '',
  }
}

function upsertCourseware(courseware) {
  const normalized = normalizeCoursewareItem(courseware)
  const index = uploadedCourseware.value.findIndex(item => item.id === normalized.id)
  if (index >= 0) {
    uploadedCourseware.value[index] = {
      ...uploadedCourseware.value[index],
      ...normalized,
    }
    return uploadedCourseware.value[index]
  }

  uploadedCourseware.value.unshift(normalized)
  return normalized
}

function stopParsePolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function pollParseStatus(coursewareId) {
  const maxAttempts = 30
  let attempts = 0

  stopParsePolling()
  pollTimer = window.setInterval(async () => {
    attempts += 1
    if (attempts > maxAttempts) {
      stopParsePolling()
      uploadStatus.value = { status: 'error', message: '解析超时，请稍后到资源详情页查看。' }
      return
    }

    try {
      const response = await getCoursewareDetail(coursewareId)
      const courseware = upsertCourseware({
        id: response.data?.coursewareId || coursewareId,
        name: response.data?.name || latestCourseware.value?.name,
        status: response.data?.status,
        createdAt: response.data?.createdAt || latestCourseware.value?.createdAt,
        updatedAt: response.data?.updatedAt,
        currentTaskStatus: response.data?.currentTaskStatus,
      })

      if (['PARSED', 'READY', 'FAILED'].includes(courseware.status)) {
        stopParsePolling()
      }

      const statusMeta = getCoursewareStatusMeta(courseware.status)
      uploadStatus.value = {
        status: courseware.status === 'FAILED' ? 'error' : 'success',
        message:
          courseware.status === 'READY'
            ? '课件已就绪，可以查看讲稿或进入课堂。'
            : `当前进度：${statusMeta.text}`,
        progress: 100,
      }
    } catch {
      // 轮询期间的瞬时错误不打断主流程。
    }
  }, 3000)
}

async function handleFileSelected(file) {
  if (uploadStatus.value?.status === 'uploading') {
    return
  }

  lastSelectedFile.value = file
  stopParsePolling()
  uploadError.value = null
  uploadStatus.value = {
    status: 'uploading',
    message: '正在上传课件...',
    progress: 0,
  }

  try {
    const response = await uploadCourseware(file, file.name, {
      timeout: 120000,
      onUploadProgress: progressEvent => {
        const total = progressEvent.total
        if (Number.isFinite(total) && total > 0) {
          const percent = Math.round((progressEvent.loaded / total) * 100)
          uploadStatus.value = {
            status: 'uploading',
            message: `正在上传课件... ${percent}%`,
            progress: percent,
          }
        }
      },
    })

    const coursewareId = response.data?.coursewareId
    latestCoursewareId.value = coursewareId
    upsertCourseware({
      id: coursewareId,
      name: file.name,
      status: 'PARSING',
      createdAt: new Date().toISOString(),
    })

    uploadStatus.value = {
      status: 'success',
      message: '上传成功，系统正在解析课件。',
      progress: 100,
    }

    pollParseStatus(coursewareId)
  } catch (error) {
    uploadStatus.value = { status: 'error', message: '上传失败，请稍后重试。' }
    uploadError.value = getErrorMessage(error, '上传失败，请稍后重试。')
  }
}

async function retryLastUpload() {
  if (!lastSelectedFile.value) {
    return
  }
  await handleFileSelected(lastSelectedFile.value)
}

function handleError(error) {
  uploadError.value = getErrorMessage(error, '文件校验失败，请检查格式后重试。')
}

function openDetail(courseware) {
  router.push({ name: 'ResourceDetail', params: { coursewareId: courseware.id } })
}

function openScript(courseware) {
  router.push({ name: 'Script', params: { coursewareId: courseware.id } })
}

function enterLecture(courseware) {
  router.push({ name: 'Lecture', params: { coursewareId: courseware.id } })
}

async function loadCoursewareList() {
  try {
    const response = await listCourseware()
    if (Array.isArray(response.data?.items)) {
      uploadedCourseware.value = response.data.items.map(normalizeCoursewareItem)
    }
  } catch {
    // 列表加载失败不影响上传主流程。
  }
}

onMounted(() => {
  loadCoursewareList()
})

onUnmounted(() => {
  stopParsePolling()
})
</script>

<style scoped>
.upload-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
}

.upload-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) 320px;
  gap: 1.25rem;
}

.section-title {
  font-size: clamp(1.8rem, 3vw, 2.4rem);
}

.upload-main-card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.upload-status-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem;
  border: 1px solid rgba(131, 141, 184, 0.12);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.76);
}

.status-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.status-label {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.status-summary h3 {
  margin: 0.35rem 0 0;
  font-size: 1.25rem;
}

.status-text {
  margin: 0.55rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.progress-track {
  width: 100%;
  height: 0.65rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(123, 133, 159, 0.14);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
  transition: width 0.3s ease;
}

.next-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.upload-side-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.side-card {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.side-card h3 {
  margin: 0;
  font-size: 1.1rem;
}

.side-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.flow-list {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
  line-height: 1.9;
}

.inline-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 0.95rem 1rem;
  border: 1px solid rgba(230, 84, 106, 0.15);
  border-radius: var(--radius-md);
  color: #b93f59;
  background: rgba(230, 84, 106, 0.08);
}

.inline-error__actions {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
}

.inline-error button {
  color: inherit;
  font-weight: 600;
  cursor: pointer;
}

@media (max-width: 1024px) {
  .upload-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .upload-hero,
  .status-summary {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 640px) {
  .next-actions {
    flex-direction: column;
  }
}
</style>

