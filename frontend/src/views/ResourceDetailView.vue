<template>
  <div class="resource-detail-page">
    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">课件详情</span>
          <h1 class="page-title">{{ detail?.name || coursewareId }}</h1>
          <p class="page-description">
            这里展示课件解析、讲稿生成、共享课程号和课堂入口的当前可用状态。
          </p>
        </div>
        <AppButton variant="secondary" @click="router.push('/classroom')">返回课堂资源页</AppButton>
      </div>
    </section>

    <section class="page-shell page-section">
      <div v-if="errorMessage" class="inline-error">
        <span>{{ errorMessage }}</span>
        <button type="button" @click="loadDetail">重试</button>
      </div>

      <AppCard v-if="loading" tone="glass" class="state-card">正在加载课件资源...</AppCard>

      <div v-else-if="detail" class="detail-layout">
        <AppCard tone="glass" class="detail-card">
          <div class="detail-card__header">
            <div>
              <span class="eyebrow">当前状态</span>
              <h2>{{ statusMeta.text }}</h2>
            </div>
            <StatusBadge :label="statusMeta.text" :tone="statusMeta.tone" />
          </div>

          <dl class="detail-list">
            <div>
              <dt>课件 ID</dt>
              <dd>{{ detail.coursewareId || coursewareId }}</dd>
            </div>
            <div>
              <dt>文件类型</dt>
              <dd>{{ detail.fileType || '未知' }}</dd>
            </div>
            <div>
              <dt>任务状态</dt>
              <dd>{{ detail.currentTaskStatus || '等待调度' }}</dd>
            </div>
            <div>
              <dt>访问方式</dt>
              <dd>{{ accessModeLabel }}</dd>
            </div>
            <div>
              <dt>课程号</dt>
              <dd>{{ detail.courseCode || '未设置' }}</dd>
            </div>
            <div>
              <dt>更新时间</dt>
              <dd>{{ detail.updatedAt || detail.createdAt || '未知' }}</dd>
            </div>
          </dl>

          <p class="status-explain">{{ statusExplain }}</p>
        </AppCard>

        <AppCard tone="accent" class="detail-card">
          <span class="eyebrow">下一步</span>
          <div class="action-stack">
            <AppButton
              v-if="canGenerateScript"
              :disabled="actionLoading"
              @click="handleGenerateScript"
            >
              {{ actionLoading ? '正在提交...' : '生成讲稿' }}
            </AppButton>
            <AppButton
              v-if="canViewScript"
              variant="secondary"
              @click="router.push(buildSharedRouteLocation('Script'))"
            >
              查看讲稿
            </AppButton>
            <AppButton
              v-if="canEnterLecture"
              @click="router.push(buildSharedRouteLocation('Lecture'))"
            >
              进入课堂
            </AppButton>
            <AppButton variant="secondary" @click="loadDetail">刷新状态</AppButton>
          </div>
        </AppCard>
      </div>

      <AppCard v-else tone="glass">
        <EmptyState
          title="未找到课件资源"
          description="请回到课堂资源页确认该资源是否仍然存在。"
          action-label="返回课堂资源页"
          @action="router.push('/classroom')"
        />
      </AppCard>
    </section>

    <section v-if="detail && canManageCourseCode" class="page-shell page-section">
      <AppCard class="course-code-card" tone="glass">
        <div class="course-code-card__header">
          <div>
            <span class="eyebrow">课程号共享</span>
            <h2 class="page-title section-title">设置学生访问课程号</h2>
            <p class="page-description">
              教师为这份课件设置课程号后，学生即可在课堂资源页输入相同课程号访问它。
            </p>
          </div>
        </div>

        <div class="course-code-form">
          <input
            v-model.trim="courseCodeInput"
            class="app-input"
            type="text"
            maxlength="64"
            placeholder="例如：ML-2026-A"
          />
          <div class="course-code-actions">
            <AppButton :disabled="courseCodeLoading" @click="saveCourseCode">
              {{ courseCodeLoading ? '保存中...' : '保存课程号' }}
            </AppButton>
            <AppButton
              variant="secondary"
              :disabled="courseCodeLoading || !detail.courseCode"
              @click="clearCourseCode"
            >
              清除课程号
            </AppButton>
          </div>
        </div>
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { generateScript, getCoursewareDetail, updateCoursewareCourseCode } from '@/api/courseware'
import { getCoursewareStatusMeta } from '@/constants/courseware'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const coursewareId = String(route.params.coursewareId || '')
const detail = ref(null)
const loading = ref(false)
const actionLoading = ref(false)
const courseCodeLoading = ref(false)
const errorMessage = ref('')
const courseCodeInput = ref('')
const routeCourseCode = computed(() => String(route.query.courseCode || '').trim().toUpperCase())

const normalizedStatus = computed(() => String(detail.value?.status || '').trim().toUpperCase())
const statusMeta = computed(() => getCoursewareStatusMeta(normalizedStatus.value))
const accessMode = computed(() => String(detail.value?.accessMode || 'OWNED').trim().toUpperCase())
const accessModeLabel = computed(() => (accessMode.value === 'SHARED' ? '共享访问' : '我的课件'))
const canModifyCourseware = computed(() => accessMode.value !== 'SHARED')
const canManageCourseCode = computed(() => canModifyCourseware.value && authStore.isTeacher)
const canGenerateScript = computed(() => canModifyCourseware.value && normalizedStatus.value === 'PARSED')
const canViewScript = computed(() => ['GENERATING_SCRIPT', 'READY'].includes(normalizedStatus.value))
const canEnterLecture = computed(() => normalizedStatus.value === 'READY')

const statusExplain = computed(() => {
  switch (normalizedStatus.value) {
    case 'UPLOADED':
      return '文件已上传，等待解析任务开始或完成。'
    case 'PARSING':
      return '课件正在解析中，请稍后刷新状态。'
    case 'PARSED':
      return canModifyCourseware.value ? '课件解析已完成，可以生成讲稿。' : '教师课件已解析完成，等待进一步生成讲稿。'
    case 'GENERATING_SCRIPT':
      return '讲稿正在生成中，可以进入讲稿页查看进度。'
    case 'READY':
      return accessMode.value === 'SHARED'
        ? '当前通过课程号共享访问该课件，可以进入讲稿页或课堂页。'
        : '讲稿和课堂入口已经准备好。'
    case 'FAILED':
      return '课件处理失败，请根据错误信息重新处理或重新导入。'
    default:
      return '当前状态暂不明确，请刷新后再试。'
  }
})

function normalizeDetail(payload) {
  return {
    coursewareId: payload?.coursewareId || payload?.id || coursewareId,
    name: payload?.name || '未命名课件',
    status: payload?.status || 'UPLOADED',
    currentTaskStatus: payload?.currentTaskStatus || '',
    fileType: payload?.fileType || '',
    courseCode: payload?.courseCode || '',
    accessMode: payload?.accessMode || 'OWNED',
    createdAt: payload?.createdAt || '',
    updatedAt: payload?.updatedAt || '',
  }
}

async function loadDetail() {
  if (!coursewareId) {
    errorMessage.value = '课件 ID 缺失。'
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getCoursewareDetail(coursewareId)
    detail.value = normalizeDetail(response.data)
    courseCodeInput.value = detail.value.courseCode || ''
  } catch (error) {
    detail.value = null
    errorMessage.value = getErrorMessage(error, '加载课件详情失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function handleGenerateScript() {
  actionLoading.value = true
  errorMessage.value = ''
  try {
    await generateScript(coursewareId)
    await router.push(buildSharedRouteLocation('Script'))
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '生成讲稿失败，请稍后重试。')
  } finally {
    actionLoading.value = false
  }
}

async function saveCourseCode() {
  courseCodeLoading.value = true
  errorMessage.value = ''
  try {
    const response = await updateCoursewareCourseCode(coursewareId, courseCodeInput.value)
    courseCodeInput.value = response.data?.courseCode || ''
    await loadDetail()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '更新课程号失败，请稍后重试。')
  } finally {
    courseCodeLoading.value = false
  }
}

async function clearCourseCode() {
  courseCodeInput.value = ''
  await saveCourseCode()
}

function buildSharedRouteLocation(name) {
  return {
    name,
    params: { coursewareId },
    query: routeCourseCode.value ? { courseCode: routeCourseCode.value } : undefined,
  }
}

onMounted(() => {
  authStore.restore()
  if (authStore.isStudent && routeCourseCode.value) {
    authStore.setActiveCourseCode(routeCourseCode.value)
  }
  loadDetail()
})
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 1.2rem;
}

.detail-card,
.course-code-card {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.detail-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.detail-card__header h2 {
  margin: 0.35rem 0 0;
}

.detail-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
  margin: 0;
}

.detail-list div {
  padding: 0.9rem;
  border: 1px solid rgba(148, 157, 188, 0.12);
  border-radius: var(--radius-md);
  background: rgba(248, 250, 255, 0.86);
}

.detail-list dt {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.detail-list dd {
  margin: 0.35rem 0 0;
  color: var(--text-primary);
  font-weight: 700;
  word-break: break-all;
}

.status-explain {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.action-stack {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.course-code-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: center;
}

.course-code-actions {
  display: flex;
  gap: 0.75rem;
}

.state-card {
  min-height: 12rem;
  display: grid;
  place-items: center;
  color: var(--text-secondary);
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

.inline-error button {
  color: inherit;
  font-weight: 600;
  cursor: pointer;
}

@media (max-width: 900px) {
  .detail-layout,
  .detail-list,
  .course-code-form {
    grid-template-columns: 1fr;
  }

  .course-code-actions {
    flex-direction: column;
  }
}
</style>
