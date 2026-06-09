<template>
  <div class="course-resource-import-page">
    <section class="page-shell page-section import-hero">
      <div class="hero-copy">
        <span class="eyebrow">课程资源导入</span>
        <h1 class="page-title">从超星课程导入课件资源</h1>
        <p class="page-description">
          使用你显式提供的课程 URL 或课程参数，结合当前已授权的 Cookie / Authorization，
          自动发现课件图片、PDF、PPT 与附件资源，并在需要时合成为可解析的 PDF。
        </p>

        <div class="hero-actions">
          <AppButton size="lg" @click="scrollToForm">开始导入</AppButton>
          <AppButton variant="secondary" size="lg" @click="router.push('/imports/upload')">
            改为上传本地课件
          </AppButton>
        </div>

        <div class="hero-trust-list">
          <div class="trust-item">
            <strong>只使用本次授权信息</strong>
            <span>Cookie / Authorization 仅用于当前导入任务，不写入浏览器 localStorage。</span>
          </div>
          <div class="trust-item">
            <strong>不会展示完整 Cookie</strong>
            <span>输入框默认掩码显示，页面也不会回显完整授权内容。</span>
          </div>
          <div class="trust-item">
            <strong>只访问超星课程域名</strong>
            <span>仅允许 `chaoxing.com` 子域课程链接，避免错误跳转到无关站点。</span>
          </div>
        </div>
      </div>

      <AppCard class="hero-panel" tone="accent">
        <div class="hero-panel__header">
          <span class="pill">导入阶段</span>
          <StatusBadge :label="taskStatusMeta.text" :tone="taskStatusMeta.tone" />
        </div>

        <div class="hero-stage-list">
          <div
            v-for="item in stageItems"
            :key="item.status"
            class="hero-stage-item"
            :class="`state-${item.state}`"
          >
            <span class="hero-stage-item__dot"></span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.description }}</p>
            </div>
          </div>
        </div>
      </AppCard>
    </section>

    <section ref="formSectionRef" class="page-shell page-section import-layout">
      <AppCard class="import-form-card" tone="accent">
        <div class="section-header import-form-card__header">
          <div>
            <span class="eyebrow">导入设置</span>
            <h2 class="page-title section-title">填写课程信息</h2>
            <p class="page-description">
              你可以直接粘贴超星课程 URL，或者改用 `courseid / clazzid / cpi / enc`
              组合导入。系统会优先使用课程页里真实出现的资源，不会枚举未知链接。
            </p>
          </div>
        </div>

        <div class="privacy-callout">
          <strong>安全提示</strong>
          <p>
            授权信息只用于本次访问；如果登录态失效，系统会提示“未授权或登录已失效”，不会自动登录或绕过验证码。
          </p>
        </div>

        <div class="chaoxing-auth-card">
          <div class="chaoxing-auth-card__copy">
            <span class="eyebrow">推荐授权方式</span>
            <h3>学习通扫码授权</h3>
            <p>
              系统会打开超星官方扫码登录页并截取二维码。你用学习通 App 扫码确认后，Cookie 只保存在后端临时会话中，
              前端不会接触完整 Cookie。
            </p>
            <div class="chaoxing-auth-card__actions">
              <AppButton type="button" :disabled="authLoading || isProcessing" @click="startChaoxingAuth">
                {{ chaoxingAuth?.sessionId ? '重新生成二维码' : '生成扫码二维码' }}
              </AppButton>
              <AppButton
                v-if="chaoxingAuth?.sessionId"
                type="button"
                variant="secondary"
                :disabled="authLoading"
                @click="disconnectChaoxingAuth"
              >
                断开授权
              </AppButton>
            </div>
          </div>

          <div class="chaoxing-auth-card__qr">
            <div v-if="authQrCodeUrl && authStatus !== 'AUTHORIZED'" class="qr-box">
              <img :src="authQrCodeUrl" alt="超星扫码登录二维码" />
            </div>
            <div v-else class="qr-placeholder" :class="{ authorized: isChaoxingAuthorized }">
              <strong>{{ isChaoxingAuthorized ? '已授权' : '等待生成二维码' }}</strong>
              <span>{{ authStatusText }}</span>
            </div>
            <StatusBadge
              :label="authStatusText"
              :tone="isChaoxingAuthorized ? 'success' : authStatus === 'FAILED' || authStatus === 'EXPIRED' ? 'danger' : 'info'"
            />
          </div>
        </div>

        <div v-if="authError" class="inline-error">
          <span>{{ authError }}</span>
          <button type="button" @click="authError = ''">关闭</button>
        </div>

        <form class="import-form" @submit.prevent="submitTask">
          <div class="field-block">
            <label class="field-label" for="course-url">超星课程 URL</label>
            <input
              id="course-url"
              v-model.trim="form.url"
              class="app-input"
              type="text"
              autocomplete="off"
              placeholder="https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=..."
            />
            <p class="field-help">如果课程 URL 已经包含 `courseid / clazzid / cpi / enc`，优先填写这里。</p>
          </div>

          <div class="divider-line">
            <span>或者手动填写课程参数</span>
          </div>

          <div class="param-grid">
            <div class="field-block">
              <label class="field-label" for="courseid">courseid</label>
              <input
                id="courseid"
                v-model.trim="form.courseid"
                class="app-input"
                type="text"
                autocomplete="off"
                placeholder="260728285"
              />
            </div>

            <div class="field-block">
              <label class="field-label" for="clazzid">clazzid</label>
              <input
                id="clazzid"
                v-model.trim="form.clazzid"
                class="app-input"
                type="text"
                autocomplete="off"
                placeholder="139811358"
              />
            </div>

            <div class="field-block">
              <label class="field-label" for="cpi">cpi</label>
              <input
                id="cpi"
                v-model.trim="form.cpi"
                class="app-input"
                type="text"
                autocomplete="off"
                placeholder="356891153"
              />
            </div>

            <div class="field-block">
              <label class="field-label" for="enc">enc</label>
              <input
                id="enc"
                v-model.trim="form.enc"
                class="app-input"
                type="text"
                autocomplete="off"
                placeholder="2448a3080846a1ab7a7c597107a9c576"
              />
            </div>
          </div>

          <details class="advanced-panel" :open="showAdvanced" @toggle="syncAdvancedPanelState">
            <summary>高级授权信息</summary>

            <div class="advanced-panel__body">
              <div class="field-block">
                <label class="field-label" for="cookie-input">Cookie</label>
                <input
                  id="cookie-input"
                  v-model.trim="form.cookie"
                  class="app-input"
                  type="password"
                  autocomplete="off"
                  spellcheck="false"
                  placeholder="本次访问所需的 Cookie"
                />
                <p class="field-help">页面不会展示完整 Cookie，提交成功后会立即清空当前输入框。</p>
              </div>

              <div class="field-block">
                <label class="field-label" for="authorization-input">Authorization</label>
                <input
                  id="authorization-input"
                  v-model.trim="form.authorization"
                  class="app-input"
                  type="password"
                  autocomplete="off"
                  spellcheck="false"
                  placeholder="可选，若课程接口要求 Authorization 可填写"
                />
              </div>

              <div class="field-block">
                <label class="field-label" for="referer-input">Referer</label>
                <input
                  id="referer-input"
                  v-model.trim="form.referer"
                  class="app-input"
                  type="text"
                  autocomplete="off"
                  placeholder="可选，默认会回退到课程 URL"
                />
              </div>

              <div class="advanced-note">
                <p>如果没有权限，系统会提示“未授权或登录已失效”。</p>
                <p>Cookie / Authorization 只在本次任务请求中使用，不会保存到浏览器本地存储。</p>
              </div>
            </div>
          </details>

          <div class="options-grid">
            <label class="option-item">
              <input v-model="form.buildPdf" type="checkbox" />
              <span>自动合成课件图片为 PDF</span>
            </label>
            <label class="option-item">
              <input v-model="form.autoParse" type="checkbox" />
              <span>自动进入课件解析</span>
            </label>
          </div>

          <div v-if="formError" class="inline-error">
            <span>{{ formError }}</span>
            <button type="button" @click="formError = ''">关闭</button>
          </div>

          <div class="form-actions">
            <AppButton type="submit" :disabled="!canSubmit || isSubmitting">
              {{ submitButtonText }}
            </AppButton>
            <AppButton variant="secondary" :disabled="isProcessing" @click="resetForm">
              重置表单
            </AppButton>
            <AppButton
              v-if="canCancelTask"
              variant="secondary"
              :disabled="actionLoading"
              @click="cancelTask"
            >
              取消任务
            </AppButton>
            <AppButton
              v-if="canRetryTask"
              variant="secondary"
              :disabled="actionLoading"
              @click="retryTask"
            >
              重新执行
            </AppButton>
          </div>
        </form>
      </AppCard>

      <div class="import-side-column">
        <AppCard class="task-summary-card" tone="glass">
          <div class="task-summary-card__header">
            <div>
              <span class="task-summary-card__label">当前任务</span>
              <h3>{{ task?.taskId || '尚未创建导入任务' }}</h3>
            </div>
            <StatusBadge :label="taskStatusMeta.text" :tone="taskStatusMeta.tone" />
          </div>

          <p class="task-summary-card__message">{{ taskMessage }}</p>

          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${taskProgress}%` }"></div>
          </div>
          <div class="progress-meta">
            <span>进度 {{ taskProgress }}%</span>
            <span v-if="task?.coursewareId">课件 ID：{{ task.coursewareId }}</span>
          </div>

          <div class="task-stats-grid">
            <div class="task-stat">
              <span>发现资源</span>
              <strong>{{ task?.discoveredCount || 0 }}</strong>
            </div>
            <div class="task-stat">
              <span>筛选下载</span>
              <strong>{{ task?.selectedCount || 0 }}</strong>
            </div>
            <div class="task-stat">
              <span>已下载</span>
              <strong>{{ task?.downloadedCount || 0 }}</strong>
            </div>
            <div class="task-stat">
              <span>已忽略</span>
              <strong>{{ task?.ignoredCount || 0 }}</strong>
            </div>
          </div>

          <div v-if="coursewareDetail" class="courseware-status">
            <div>
              <span class="task-summary-card__label">课件解析状态</span>
              <strong>{{ coursewareStatusMeta.text }}</strong>
            </div>
            <StatusBadge :label="coursewareStatusMeta.text" :tone="coursewareStatusMeta.tone" />
          </div>
        </AppCard>

        <AppCard class="result-card" tone="subtle">
          <h3>完成后可继续</h3>
          <div class="result-actions">
            <AppButton
              variant="secondary"
              size="sm"
              :disabled="!canOpenGeneratedPdf"
              @click="openGeneratedPdf"
            >
              查看生成 PDF
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              :disabled="!canOpenParseResult"
              @click="openParseResult"
            >
              进入课件解析结果
            </AppButton>
            <AppButton size="sm" :disabled="!canOpenLecture" @click="openLecturePage">
              进入讲课页
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              :disabled="!canOpenScript"
              @click="openScriptPage"
            >
              查看讲稿
            </AppButton>
          </div>
          <p class="result-note">{{ resultHint }}</p>
          <p v-if="task?.generatedPdf" class="result-path">
            生成 PDF 路径：<span>{{ task.generatedPdf }}</span>
          </p>
        </AppCard>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">文件列表</span>
          <h2 class="page-title section-title">已发现与下载的课件资源</h2>
          <p class="page-description">
            展示当前导入任务识别到的课件图片、原始课件与附件资源，并标注类型、状态、置信度和分类原因。
          </p>
        </div>
      </div>

      <div v-if="pageError" class="inline-error">
        <span>{{ pageError }}</span>
        <button type="button" @click="pageError = ''">关闭</button>
      </div>

      <AppCard v-if="files.length" class="files-card" tone="glass">
        <div class="files-card__toolbar">
          <div>
            <strong>{{ files.length }}</strong>
            <span>项资源记录</span>
          </div>
          <StatusBadge :label="taskStatusMeta.text" :tone="taskStatusMeta.tone" />
        </div>

        <div class="file-table">
          <div class="file-table__head">
            <span>文件名</span>
            <span>类型</span>
            <span>状态</span>
            <span>置信度</span>
            <span>分类原因</span>
          </div>

          <div v-for="item in files" :key="`${item.fileName}-${item.resourceKind}`" class="file-row">
            <div class="file-row__name">
              <strong>{{ item.fileName }}</strong>
            </div>
            <div class="file-row__kind">
              <span class="pill">{{ formatResourceKind(item.resourceKind) }}</span>
            </div>
            <div class="file-row__status">
              <StatusBadge :label="fileStatusMeta(item.status).text" :tone="fileStatusMeta(item.status).tone" compact />
            </div>
            <div class="file-row__confidence">
              {{ formatConfidence(item.confidence) }}
            </div>
            <div class="file-row__reason">
              {{ item.reason || '等待分类结果' }}
            </div>
          </div>
        </div>
      </AppCard>

      <AppCard v-else tone="glass">
        <EmptyState
          title="还没有课件资源记录"
          description="提交导入任务后，这里会显示识别出的 slide_image、courseware_file、attachment 等资源。"
        />
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  cancelCourseResourceImportTask,
  createCourseResourceImportTask,
  getCourseResourceImportTask,
  getCourseResourceImportTaskFiles,
  retryCourseResourceImportTask,
} from '@/api/courseResourceImport'
import { getCoursewareDetail } from '@/api/courseware'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { getCoursewareStatusMeta } from '@/constants/courseware'
import { useChaoxingAuthStore } from '@/stores/chaoxingAuth'
import { parseChaoxingCourseUrl } from '@/utils/chaoxing'
import { getErrorMessage } from '@/utils'

const router = useRouter()
const chaoxingAuthStore = useChaoxingAuthStore()

const TASK_STATUS_META = {
  PENDING: {
    text: '等待调度',
    tone: 'neutral',
    description: '任务已创建，等待开始访问课程页面。',
  },
  FETCHING: {
    text: '获取课程页面',
    tone: 'info',
    description: '正在使用授权信息访问超星课程页。',
  },
  DISCOVERING: {
    text: '发现资源',
    tone: 'accent',
    description: '正在扫描课程页中的课件图片、PDF、PPT 与附件。',
  },
  CLASSIFYING: {
    text: '筛选资源',
    tone: 'warning',
    description: '正在过滤站点静态资源，只保留课件相关内容。',
  },
  DOWNLOADING: {
    text: '下载课件资源',
    tone: 'accent',
    description: '正在下载课件图片、原始课件文件和相关附件。',
  },
  BUILDING_PDF: {
    text: '合成 PDF',
    tone: 'warning',
    description: '正在把连续课件页图片合成为 courseware_from_images.pdf。',
  },
  PARSING: {
    text: '课件解析',
    tone: 'info',
    description: '已触发现有课件解析流程，正在准备后续讲稿入口。',
  },
  READY: {
    text: '完成',
    tone: 'success',
    description: '导入任务已完成，可以继续查看 PDF、解析结果和后续页面。',
  },
  FAILED: {
    text: '失败',
    tone: 'danger',
    description: '导入任务执行失败。',
  },
  CANCELLED: {
    text: '已取消',
    tone: 'neutral',
    description: '导入任务已取消。',
  },
}

const STAGE_FLOW = [
  {
    status: 'FETCHING',
    title: '获取课程页面',
    description: '校验 URL 与授权信息，拉取课程 HTML。',
  },
  {
    status: 'DISCOVERING',
    title: '发现资源',
    description: '识别页面中真实出现的课件文件与图片资源。',
  },
  {
    status: 'CLASSIFYING',
    title: '筛选课件图片 / 附件',
    description: '过滤图标、按钮、插件和站点公共资源。',
  },
  {
    status: 'DOWNLOADING',
    title: '下载课件资源',
    description: '下载 slide_image、courseware_file 与 attachment。',
  },
  {
    status: 'BUILDING_PDF',
    title: '合成 PDF',
    description: '把连续课件页图片合成为可解析 PDF。',
  },
  {
    status: 'PARSING',
    title: '课件解析',
    description: '复用现有课件解析链路，准备进入讲稿页。',
  },
  {
    status: 'READY',
    title: '完成',
    description: '导入结束，等待你继续查看结果。',
  },
]

const FILE_STATUS_META = {
  SUCCESS: { text: '成功', tone: 'success' },
  FAILED: { text: '失败', tone: 'danger' },
  SKIPPED: { text: '已复用', tone: 'info' },
  IGNORED: { text: '已忽略', tone: 'neutral' },
}

const RESOURCE_KIND_LABELS = {
  slide_image: 'slide_image',
  courseware_file: 'courseware_file',
  attachment: 'attachment',
  content_image: 'content_image',
  ui_asset: 'ui_asset',
  metadata: 'metadata',
  unknown: 'unknown',
}

const POLL_INTERVAL_MS = 3000
const AUTH_POLL_INTERVAL_MS = 2500
const TERMINAL_STATUSES = new Set(['READY', 'FAILED', 'CANCELLED'])
const AUTH_TERMINAL_STATUSES = new Set(['AUTHORIZED', 'EXPIRED', 'FAILED', 'CLOSED'])

const formSectionRef = ref(null)
const showAdvanced = ref(false)
const formError = ref('')
const pageError = ref('')
const isSubmitting = ref(false)
const actionLoading = ref(false)
const authError = ref('')
const task = ref(null)
const files = ref([])
const coursewareDetail = ref(null)

const form = reactive({
  url: '',
  courseid: '',
  clazzid: '',
  cpi: '',
  enc: '',
  authSessionId: '',
  cookie: '',
  authorization: '',
  referer: '',
  buildPdf: true,
  autoParse: true,
})

let pollTimer = null
let authPollTimer = null

const normalizedTaskStatus = computed(() => normalizeTaskStatus(task.value?.status))
const taskStatusMeta = computed(() => TASK_STATUS_META[normalizedTaskStatus.value] || TASK_STATUS_META.PENDING)
const taskProgress = computed(() => Number(task.value?.progress || 0))
const isProcessing = computed(() => Boolean(task.value?.taskId) && !TERMINAL_STATUSES.has(normalizedTaskStatus.value))
const canCancelTask = computed(() => Boolean(task.value?.taskId) && !TERMINAL_STATUSES.has(normalizedTaskStatus.value))
const canRetryTask = computed(() => ['FAILED', 'CANCELLED'].includes(normalizedTaskStatus.value))

const submitButtonText = computed(() => {
  if (isSubmitting.value) {
    return '正在提交导入任务...'
  }
  if (isProcessing.value) {
    return '导入任务执行中'
  }
  return '开始导入课件资源'
})

const taskMessage = computed(() => {
  if (!task.value) {
    return '提交任务后，这里会显示当前阶段、下载统计和后续解析入口。'
  }

  if (normalizedTaskStatus.value === 'FAILED') {
    return mapFriendlyImportMessage(task.value.message)
  }

  if (normalizedTaskStatus.value === 'CANCELLED') {
    return '导入任务已取消。你可以调整授权信息后重新提交。'
  }

  if (normalizedTaskStatus.value === 'READY') {
    if (!task.value.selectedCount) {
      return '没有发现课件资源，请确认课程页中确实存在 PPT、PDF、附件或课件页图片。'
    }

    if (task.value.coursewareId && coursewareDetail.value) {
      const status = normalizeCoursewareStatus(coursewareDetail.value.status)
      if (status === 'PARSING') {
        return '课件资源已导入，自动解析正在继续处理，稍后可进入解析结果页。'
      }
      if (status === 'PARSED') {
        return '课件解析已完成，可以进入解析结果页并继续生成讲稿。'
      }
      if (status === 'READY') {
        return '课件、讲稿与讲课入口都已准备完成。'
      }
      if (status === 'FAILED') {
        return '课件资源已导入，但自动解析失败，请稍后重试或重新导入。'
      }
    }

    if (task.value.generatedPdf) {
      return '课件资源已导入，并已生成可继续解析的图片合成 PDF。'
    }

    return '导入任务已完成。'
  }

  return TASK_STATUS_META[normalizedTaskStatus.value]?.description || task.value.message || '任务正在处理中。'
})

const coursewareStatusMeta = computed(() => {
  return getCoursewareStatusMeta(coursewareDetail.value?.status || '')
})

const chaoxingAuth = computed(() => chaoxingAuthStore.session)

const authLoading = computed(() => chaoxingAuthStore.loading)

const authStatus = computed(() => chaoxingAuthStore.status)

const isChaoxingAuthorized = computed(() => chaoxingAuthStore.isAuthorized)

const authQrCodeUrl = computed(() => chaoxingAuthStore.qrCodeUrl)

const authStatusText = computed(() => {
  const status = authStatus.value
  if (status === 'AUTHORIZED') {
    return '授权成功，可以提交导入'
  }
  if (status === 'WAITING_SCAN') {
    return '等待学习通扫码确认'
  }
  if (status === 'WAITING_QR' || status === 'CREATED') {
    return '正在生成登录二维码'
  }
  if (status === 'EXPIRED') {
    return '二维码已过期，请重新创建'
  }
  if (status === 'FAILED') {
    return '授权失败，请重试'
  }
  if (status === 'CLOSED') {
    return '授权已断开'
  }
  return '尚未创建授权会话'
})

const canSubmit = computed(() => {
  return !isSubmitting.value && !isProcessing.value && hasSourceInput() && hasAuthorizationInput()
})

const canOpenGeneratedPdf = computed(() => Boolean(task.value?.generatedPdf))
const canOpenParseResult = computed(() => {
  if (!task.value?.coursewareId || !coursewareDetail.value) {
    return false
  }
  return ['PARSED', 'GENERATING_SCRIPT', 'READY'].includes(normalizeCoursewareStatus(coursewareDetail.value.status))
})
const canOpenScript = computed(() => Boolean(task.value?.coursewareId) && normalizeCoursewareStatus(coursewareDetail.value?.status) === 'READY')
const canOpenLecture = computed(() => Boolean(task.value?.coursewareId) && normalizeCoursewareStatus(coursewareDetail.value?.status) === 'READY')

const resultHint = computed(() => {
  if (!task.value) {
    return '完成后你可以查看生成的 PDF，并根据自动解析状态进入讲稿页或讲课页。'
  }

  if (task.value.generatedPdf && !task.value.coursewareId) {
    return 'PDF 已生成；如果没有开启自动解析，可稍后用该 PDF 继续走本地课件上传流程。'
  }

  if (task.value.coursewareId && !coursewareDetail.value) {
    return '导入完成后会继续轮询课件解析状态，并在准备好时开放后续入口。'
  }

  const coursewareStatus = normalizeCoursewareStatus(coursewareDetail.value?.status)
  if (coursewareStatus === 'PARSING') {
    return '自动解析已触发，课件仍在后台解析中。解析完成后可先进入解析结果页，再生成讲稿。'
  }
  if (coursewareStatus === 'PARSED') {
    return '课件解析已完成，但讲稿还未生成。你可以先进入解析结果页，再生成讲稿。'
  }
  if (coursewareStatus === 'READY') {
    return '课件、讲稿和讲课入口都已准备好，可以直接继续后续教学流程。'
  }
  return '导入完成后会在这里展示可用的后续操作。'
})

const stageItems = computed(() => {
  return STAGE_FLOW.map((stage, index) => {
    const state = resolveStageState(stage.status, index)
    return {
      ...stage,
      state,
    }
  })
})

function scrollToForm() {
  formSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function syncAdvancedPanelState(event) {
  showAdvanced.value = Boolean(event.target?.open)
}

function hasSourceInput() {
  return Boolean(form.url.trim() || form.courseid.trim())
}

function hasAuthorizationInput() {
  return Boolean(isChaoxingAuthorized.value || form.cookie.trim() || form.authorization.trim())
}

function normalizeOptional(value) {
  const normalized = String(value || '').trim()
  return normalized || null
}

function buildPayload() {
  return {
    sourceType: 'CHAOXING_COURSE',
    url: normalizeOptional(form.url),
    courseid: normalizeOptional(form.courseid),
    clazzid: normalizeOptional(form.clazzid),
    cpi: normalizeOptional(form.cpi),
    enc: normalizeOptional(form.enc),
    authSessionId: isChaoxingAuthorized.value ? normalizeOptional(form.authSessionId) : null,
    cookie: normalizeOptional(form.cookie),
    authorization: normalizeOptional(form.authorization),
    referer: normalizeOptional(form.referer),
    buildPdf: Boolean(form.buildPdf),
    autoParse: Boolean(form.autoParse),
  }
}

function clearSensitiveInputs() {
  form.cookie = ''
  form.authorization = ''
}

function resetForm() {
  form.url = ''
  form.courseid = ''
  form.clazzid = ''
  form.cpi = ''
  form.enc = ''
  form.authSessionId = chaoxingAuthStore.sessionId || ''
  form.cookie = ''
  form.authorization = ''
  form.referer = ''
  form.buildPdf = true
  form.autoParse = true
  formError.value = ''
  showAdvanced.value = false
}

function normalizeTaskStatus(status) {
  return String(status || 'PENDING').trim().toUpperCase()
}

function normalizeCoursewareStatus(status) {
  return String(status || '').trim().toUpperCase()
}

function normalizeTask(payload) {
  return {
    taskId: payload?.taskId || '',
    status: normalizeTaskStatus(payload?.status),
    progress: Number(payload?.progress || 0),
    discoveredCount: Number(payload?.discoveredCount || 0),
    selectedCount: Number(payload?.selectedCount || 0),
    downloadedCount: Number(payload?.downloadedCount || 0),
    ignoredCount: Number(payload?.ignoredCount || 0),
    generatedPdf: payload?.generatedPdf || null,
    message: payload?.message || '',
    coursewareId: payload?.coursewareId || '',
  }
}

function normalizeFileItem(item) {
  return {
    fileName: item?.fileName || '未命名资源',
    resourceKind: item?.resourceKind || 'unknown',
    status: String(item?.status || 'UNKNOWN').trim().toUpperCase(),
    localPath: item?.localPath || '',
    confidence: typeof item?.confidence === 'number' ? item.confidence : Number(item?.confidence || 0),
    reason: item?.reason || '',
  }
}

function normalizeCoursewareDetail(payload) {
  return {
    coursewareId: payload?.coursewareId || '',
    name: payload?.name || '',
    status: normalizeCoursewareStatus(payload?.status),
    currentTaskStatus: payload?.currentTaskStatus || '',
    fileType: payload?.fileType || '',
  }
}

function mapFriendlyImportMessage(message) {
  const raw = getErrorMessage(message, '导入失败，请稍后重试。')
  const normalized = raw.toLowerCase()

  if (
    normalized.includes('unauthorized') ||
    normalized.includes('credential') ||
    normalized.includes('cookie') ||
    normalized.includes('authorization') ||
    normalized.includes('login')
  ) {
    return '未授权或登录已失效，请重新提供当前课程可用的 Cookie 或 Authorization。'
  }

  if (normalized.includes('rate limit') || normalized.includes('too frequent') || normalized.includes('429')) {
    return '请求过于频繁，请稍后重试。'
  }

  if (
    normalized.includes('chaoxing.com') ||
    normalized.includes('course url') ||
    normalized.includes('source_type')
  ) {
    return '课程 URL 或课程参数不符合要求，请确认链接属于 chaoxing.com 子域。'
  }

  if (normalized.includes('download')) {
    return '下载失败，请检查当前课程资源是否仍可访问。'
  }

  if (normalized.includes('pdf')) {
    return '合成 PDF 失败，请确认课程页图片是否完整可用。'
  }

  if (normalized.includes('no parse-ready') || normalized.includes('parse-ready')) {
    return '没有发现可继续自动解析的 PDF / PPTX 资源。'
  }

  return raw
}

function resolveStageState(stageStatus, index) {
  const currentStatus = normalizedTaskStatus.value
  const currentIndex = STAGE_FLOW.findIndex(item => item.status === currentStatus)

  if (currentStatus === 'READY') {
    return 'completed'
  }

  if (currentStatus === 'FAILED' || currentStatus === 'CANCELLED') {
    return 'pending'
  }

  if (currentIndex === -1) {
    return index === 0 ? 'current' : 'pending'
  }

  if (index < currentIndex) {
    return 'completed'
  }

  if (index === currentIndex) {
    return 'current'
  }

  return 'pending'
}

function formatResourceKind(kind) {
  return RESOURCE_KIND_LABELS[kind] || kind || 'unknown'
}

function fileStatusMeta(status) {
  return FILE_STATUS_META[String(status || '').trim().toUpperCase()] || {
    text: status || '未知',
    tone: 'neutral',
  }
}

function formatConfidence(confidence) {
  const numeric = Number(confidence)
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return '-'
  }
  return `${Math.round(numeric * 100)}%`
}

function applyChaoxingUrlParams(url) {
  const parsed = parseChaoxingCourseUrl(url)
  if (!parsed) {
    return
  }

  if (parsed.courseid) {
    form.courseid = parsed.courseid
  }
  if (parsed.clazzid) {
    form.clazzid = parsed.clazzid
  }
  if (parsed.cpi) {
    form.cpi = parsed.cpi
  }
  if (parsed.enc) {
    form.enc = parsed.enc
  }
}

function syncAuthSession(session) {
  if (!session?.sessionId) {
    form.authSessionId = ''
    return
  }
  form.authSessionId = session.sessionId
}

function stopAuthPolling() {
  if (authPollTimer) {
    window.clearInterval(authPollTimer)
    authPollTimer = null
  }
}

function startAuthPolling(sessionId) {
  stopAuthPolling()
  authPollTimer = window.setInterval(async () => {
    await refreshAuthSession(sessionId)
  }, AUTH_POLL_INTERVAL_MS)
}

async function startChaoxingAuth() {
  authError.value = ''
  formError.value = ''
  try {
    const session = await chaoxingAuthStore.createSession({
      courseUrl: normalizeOptional(form.url),
    })
    syncAuthSession(session)
    if (!AUTH_TERMINAL_STATUSES.has(authStatus.value)) {
      startAuthPolling(session.sessionId)
    }
  } catch (error) {
    authError.value = mapFriendlyImportMessage(error)
  }
}

async function refreshAuthSession(sessionId) {
  if (!sessionId) {
    return
  }
  try {
    const session = await chaoxingAuthStore.refreshSession(sessionId)
    syncAuthSession(session)
    if (AUTH_TERMINAL_STATUSES.has(authStatus.value)) {
      stopAuthPolling()
    }
  } catch (error) {
    authError.value = mapFriendlyImportMessage(error)
    stopAuthPolling()
  }
}

async function disconnectChaoxingAuth() {
  const sessionId = chaoxingAuth.value?.sessionId
  stopAuthPolling()
  form.authSessionId = ''
  if (!sessionId) {
    chaoxingAuthStore.clearSession()
    return
  }
  try {
    await chaoxingAuthStore.closeSession()
  } catch (error) {
    authError.value = mapFriendlyImportMessage(error)
  }
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(taskId) {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    await refreshTaskState(taskId)
  }, POLL_INTERVAL_MS)
}

async function refreshTaskState(taskId) {
  if (!taskId) {
    return
  }

  try {
    const [taskResponse, filesResponse] = await Promise.allSettled([
      getCourseResourceImportTask(taskId),
      getCourseResourceImportTaskFiles(taskId),
    ])

    if (taskResponse.status === 'fulfilled') {
      task.value = normalizeTask(taskResponse.value.data)
    } else {
      throw taskResponse.reason
    }

    if (filesResponse.status === 'fulfilled') {
      files.value = Array.isArray(filesResponse.value.data?.items)
        ? filesResponse.value.data.items.map(normalizeFileItem)
        : []
    }

    if (task.value?.coursewareId) {
      await refreshCoursewareState(task.value.coursewareId)
    } else {
      coursewareDetail.value = null
    }

    if (TERMINAL_STATUSES.has(normalizedTaskStatus.value)) {
      stopPolling()
    }
  } catch (error) {
    pageError.value = mapFriendlyImportMessage(error)
    stopPolling()
  }
}

async function refreshCoursewareState(coursewareId) {
  try {
    const response = await getCoursewareDetail(coursewareId)
    coursewareDetail.value = normalizeCoursewareDetail(response.data)
  } catch {
    coursewareDetail.value = null
  }
}

async function submitTask() {
  formError.value = ''
  pageError.value = ''

  if (!hasSourceInput()) {
    formError.value = '请填写超星课程 URL，或至少填写 courseid。'
    return
  }

  if (!hasAuthorizationInput()) {
    showAdvanced.value = true
    formError.value = '请先扫码授权，或在高级授权信息中提供 Cookie / Authorization。'
    return
  }

  isSubmitting.value = true
  try {
    const response = await createCourseResourceImportTask(buildPayload())
    task.value = normalizeTask(response.data)
    files.value = []
    coursewareDetail.value = null
    clearSensitiveInputs()
    await refreshTaskState(task.value.taskId)
    if (!TERMINAL_STATUSES.has(normalizedTaskStatus.value)) {
      startPolling(task.value.taskId)
    }
  } catch (error) {
    formError.value = mapFriendlyImportMessage(error)
  } finally {
    isSubmitting.value = false
  }
}

async function cancelTask() {
  if (!task.value?.taskId) {
    return
  }

  actionLoading.value = true
  try {
    const response = await cancelCourseResourceImportTask(task.value.taskId)
    task.value = normalizeTask(response.data)
    stopPolling()
  } catch (error) {
    pageError.value = mapFriendlyImportMessage(error)
  } finally {
    actionLoading.value = false
  }
}

async function retryTask() {
  if (!task.value?.taskId) {
    return
  }

  actionLoading.value = true
  pageError.value = ''
  try {
    const response = await retryCourseResourceImportTask(task.value.taskId)
    task.value = normalizeTask(response.data)
    files.value = []
    coursewareDetail.value = null
    await refreshTaskState(task.value.taskId)
    if (!TERMINAL_STATUSES.has(normalizedTaskStatus.value)) {
      startPolling(task.value.taskId)
    }
  } catch (error) {
    pageError.value = mapFriendlyImportMessage(error)
  } finally {
    actionLoading.value = false
  }
}

function toPdfTarget(path) {
  if (!path) {
    return ''
  }

  if (/^https?:\/\//i.test(path) || path.startsWith('/')) {
    return path
  }

  if (/^[a-zA-Z]:[\\/]/.test(path)) {
    return `file:///${path.replace(/\\/g, '/')}`
  }

  return path
}

function openGeneratedPdf() {
  const target = toPdfTarget(task.value?.generatedPdf)
  if (!target) {
    return
  }

  const opened = window.open(target, '_blank', 'noopener')
  if (!opened) {
    pageError.value = 'PDF 已生成，但当前浏览器阻止了直接打开。请使用页面中展示的路径在本机查看。'
  }
}

function openParseResult() {
  if (!task.value?.coursewareId) {
    return
  }
  router.push({ name: 'ResourceDetail', params: { coursewareId: task.value.coursewareId } })
}

function openScriptPage() {
  if (!task.value?.coursewareId) {
    return
  }
  router.push({ name: 'Script', params: { coursewareId: task.value.coursewareId } })
}

function openLecturePage() {
  if (!task.value?.coursewareId) {
    return
  }
  router.push({ name: 'Lecture', params: { coursewareId: task.value.coursewareId } })
}

watch(
  () => form.url,
  value => {
    applyChaoxingUrlParams(value)
  },
)

onMounted(async () => {
  stopPolling()
  stopAuthPolling()
  applyChaoxingUrlParams(form.url)
  const restored = await chaoxingAuthStore.restoreFromLocalStorage()
  syncAuthSession(restored || chaoxingAuth.value)
})

onUnmounted(() => {
  stopPolling()
  stopAuthPolling()
})
</script>

<style scoped>
.import-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 1.5rem;
  align-items: stretch;
}

.hero-copy {
  padding: 2.6rem;
  border-radius: calc(var(--radius-xl) + 0.2rem);
  border: 1px solid rgba(118, 127, 255, 0.14);
  background:
    radial-gradient(circle at top left, rgba(95, 104, 255, 0.18), transparent 32%),
    radial-gradient(circle at bottom right, rgba(72, 165, 255, 0.16), transparent 28%),
    rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-md);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  margin-top: 1.8rem;
}

.hero-trust-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 2rem;
}

.trust-item {
  padding: 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(128, 140, 182, 0.12);
  background: rgba(255, 255, 255, 0.74);
}

.trust-item strong {
  display: block;
  margin-bottom: 0.45rem;
  font-size: 1rem;
}

.trust-item span {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

.hero-panel {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.hero-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.hero-stage-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.hero-stage-item {
  display: flex;
  gap: 0.9rem;
  padding: 0.95rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(123, 134, 179, 0.12);
}

.hero-stage-item__dot {
  width: 0.9rem;
  height: 0.9rem;
  margin-top: 0.35rem;
  border-radius: 999px;
  flex-shrink: 0;
  background: rgba(111, 123, 164, 0.22);
}

.hero-stage-item strong {
  display: block;
}

.hero-stage-item p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

.hero-stage-item.state-current {
  border-color: rgba(95, 104, 255, 0.2);
  background: rgba(95, 104, 255, 0.08);
}

.hero-stage-item.state-current .hero-stage-item__dot {
  background: var(--primary-color);
}

.hero-stage-item.state-completed .hero-stage-item__dot {
  background: var(--success-color);
}

.import-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) 360px;
  gap: 1.25rem;
}

.import-form-card {
  display: flex;
  flex-direction: column;
  gap: 1.4rem;
}

.import-form-card__header {
  margin-bottom: 0;
}

.section-title {
  font-size: clamp(1.9rem, 3vw, 2.5rem);
}

.privacy-callout {
  padding: 1rem 1.05rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(121, 133, 182, 0.12);
}

.privacy-callout strong {
  display: block;
}

.privacy-callout p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

.chaoxing-auth-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 1rem;
  align-items: stretch;
  padding: 1.05rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(95, 104, 255, 0.16);
  background:
    radial-gradient(circle at top left, rgba(95, 104, 255, 0.12), transparent 34%),
    rgba(255, 255, 255, 0.78);
}

.chaoxing-auth-card__copy h3 {
  margin: 0.3rem 0 0.55rem;
  font-size: 1.2rem;
}

.chaoxing-auth-card__copy p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

.chaoxing-auth-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.chaoxing-auth-card__qr {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  align-items: center;
  justify-content: center;
}

.qr-box,
.qr-placeholder {
  display: flex;
  width: 180px;
  height: 180px;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: var(--radius-md);
  border: 1px solid rgba(122, 132, 181, 0.16);
  background: rgba(255, 255, 255, 0.9);
}

.qr-box img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.qr-placeholder {
  flex-direction: column;
  gap: 0.45rem;
  padding: 1rem;
  text-align: center;
  color: var(--text-secondary);
}

.qr-placeholder.authorized {
  color: var(--success-color);
  background: rgba(54, 179, 126, 0.08);
}

.qr-placeholder span {
  font-size: var(--font-size-xs);
  line-height: 1.5;
}

.import-form {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.field-label {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: 700;
}

.field-help {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.7;
}

.divider-line {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.divider-line::before,
.divider-line::after {
  content: '';
  height: 1px;
  flex: 1;
  background: rgba(123, 133, 178, 0.16);
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.advanced-panel {
  border: 1px solid rgba(125, 136, 182, 0.14);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.72);
}

.advanced-panel summary {
  padding: 1rem 1.05rem;
  cursor: pointer;
  font-weight: 700;
  color: var(--text-primary);
}

.advanced-panel__body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 0 1.05rem 1.05rem;
}

.advanced-note {
  padding: 0.95rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(95, 104, 255, 0.06);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.advanced-note p {
  margin: 0;
  line-height: 1.7;
}

.advanced-note p + p {
  margin-top: 0.4rem;
}

.options-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-height: 3rem;
  padding: 0.85rem 0.95rem;
  border-radius: var(--radius-md);
  border: 1px solid rgba(122, 132, 181, 0.14);
  background: rgba(255, 255, 255, 0.76);
  cursor: pointer;
}

.option-item input {
  accent-color: var(--primary-color);
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.import-side-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.task-summary-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.task-summary-card__header,
.courseware-status,
.files-card__toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.task-summary-card__label {
  display: inline-flex;
  margin-bottom: 0.35rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.task-summary-card__header h3 {
  margin: 0;
  font-size: 1.1rem;
  word-break: break-all;
}

.task-summary-card__message,
.result-note {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.progress-track {
  width: 100%;
  height: 0.68rem;
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

.progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.task-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.task-stat {
  padding: 0.9rem;
  border-radius: var(--radius-md);
  background: rgba(248, 250, 255, 0.88);
  border: 1px solid rgba(128, 139, 182, 0.12);
}

.task-stat span {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.task-stat strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 1.4rem;
}

.result-card h3 {
  margin: 0 0 1rem;
  font-size: 1.15rem;
}

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.result-path {
  margin: 0.85rem 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.7;
  word-break: break-all;
}

.result-path span {
  color: var(--text-secondary);
}

.inline-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.2rem;
  padding: 0.95rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(230, 84, 106, 0.08);
  border: 1px solid rgba(230, 84, 106, 0.15);
  color: #b93f59;
}

.inline-error button {
  color: inherit;
  font-weight: 600;
  cursor: pointer;
}

.files-card {
  overflow: hidden;
}

.files-card__toolbar strong {
  margin-right: 0.35rem;
  font-size: 1.2rem;
}

.files-card__toolbar span {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

.file-table {
  display: grid;
  gap: 0.65rem;
  margin-top: 1rem;
}

.file-table__head,
.file-row {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 160px 120px 100px minmax(0, 1.5fr);
  gap: 0.75rem;
  align-items: center;
}

.file-table__head {
  padding: 0 0.2rem 0.45rem;
  border-bottom: 1px solid rgba(125, 136, 182, 0.14);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.file-row {
  padding: 0.95rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(248, 250, 255, 0.86);
  border: 1px solid rgba(129, 140, 183, 0.12);
}

.file-row__name strong {
  display: block;
  word-break: break-word;
}

.file-row__confidence {
  font-weight: 700;
  color: var(--text-secondary);
}

.file-row__reason {
  color: var(--text-secondary);
  line-height: 1.7;
}

@media (max-width: 1180px) {
  .import-hero,
  .import-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 880px) {
  .hero-trust-list,
  .chaoxing-auth-card,
  .param-grid,
  .options-grid,
  .task-stats-grid {
    grid-template-columns: 1fr;
  }

  .file-table__head {
    display: none;
  }

  .file-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hero-copy {
    padding: 1.35rem;
  }

  .hero-actions,
  .form-actions,
  .result-actions {
    flex-direction: column;
  }

  .task-summary-card__header,
  .courseware-status,
  .files-card__toolbar,
  .progress-meta,
  .inline-error {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
