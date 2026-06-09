<template>
  <div class="resource-detail-page">
    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">课件资源详情</span>
          <h1 class="page-title">{{ detail?.name || coursewareId }}</h1>
          <p class="page-description">
            这里展示课件解析、讲稿生成和课堂入口的当前可用状态，避免在资源未准备好时误入空页面。
          </p>
        </div>
        <AppButton variant="secondary" @click="router.push('/resources')">返回资源库</AppButton>
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
              @click="router.push({ name: 'Script', params: { coursewareId } })"
            >
              查看讲稿
            </AppButton>
            <AppButton
              v-if="canEnterLecture"
              @click="router.push({ name: 'Lecture', params: { coursewareId } })"
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
          description="请回到资源库确认该资源是否仍然存在。"
          action-label="返回资源库"
          @action="router.push('/resources')"
        />
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
import { generateScript, getCoursewareDetail } from '@/api/courseware'
import { getCoursewareStatusMeta } from '@/constants/courseware'
import { getErrorMessage } from '@/utils'

const route = useRoute()
const router = useRouter()

const coursewareId = String(route.params.coursewareId || '')
const detail = ref(null)
const loading = ref(false)
const actionLoading = ref(false)
const errorMessage = ref('')

const normalizedStatus = computed(() => String(detail.value?.status || '').trim().toUpperCase())
const statusMeta = computed(() => getCoursewareStatusMeta(normalizedStatus.value))
const canGenerateScript = computed(() => normalizedStatus.value === 'PARSED')
const canViewScript = computed(() => ['GENERATING_SCRIPT', 'READY'].includes(normalizedStatus.value))
const canEnterLecture = computed(() => normalizedStatus.value === 'READY')

const statusExplain = computed(() => {
  switch (normalizedStatus.value) {
    case 'UPLOADED':
      return '文件已上传，等待解析任务开始或完成。'
    case 'PARSING':
      return '课件正在解析中，请稍后刷新状态。'
    case 'PARSED':
      return '课件解析已完成，可以生成讲稿。'
    case 'GENERATING_SCRIPT':
      return '讲稿正在生成中，可以进入讲稿页查看进度。'
    case 'READY':
      return '讲稿和课堂入口已经准备好。'
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
    await router.push({ name: 'Script', params: { coursewareId } })
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '生成讲稿失败，请稍后重试。')
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  loadDetail()
})
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 1.2rem;
}

.detail-card {
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
  .detail-list {
    grid-template-columns: 1fr;
  }
}
</style>

