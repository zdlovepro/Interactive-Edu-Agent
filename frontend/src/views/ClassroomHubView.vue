<template>
  <div class="classroom-page">
    <section class="page-shell page-section classroom-hero">
      <div>
        <span class="eyebrow">课堂</span>
        <h1 class="page-title">已导入课件与课堂入口</h1>
        <p class="page-description">
          这里负责继续上课，而不是创建资源。导入完成后的课件、讲稿和课堂播放，都从这里进入。
        </p>
      </div>

      <div class="classroom-hero__actions">
        <AppButton variant="secondary" @click="router.push('/imports')">打开导入中心</AppButton>
        <AppButton @click="router.push('/imports/upload')">上传本地课件</AppButton>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="classroom-summary">
        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">课件总数</span>
          <strong>{{ stats.total }}</strong>
          <p>包含已上传、解析中、讲稿生成中和可上课课件。</p>
        </AppCard>

        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">可直接上课</span>
          <strong>{{ stats.ready }}</strong>
          <p>状态为 `READY` 的课件可以直接进入讲稿页或课堂页。</p>
        </AppCard>

        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">处理中</span>
          <strong>{{ stats.processing }}</strong>
          <p>还在解析、补音频或生成讲稿的视频任务会显示在这里。</p>
        </AppCard>

        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">失败/需重试</span>
          <strong>{{ stats.failed }}</strong>
          <p>失败课件可以先进入详情页查看状态，再决定是否重试。</p>
        </AppCard>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="section-header classroom-section-header">
        <div>
          <span class="eyebrow">最近课件</span>
          <h2 class="page-title section-title">从这里继续讲稿、课堂和视频</h2>
        </div>

        <AppButton variant="secondary" :disabled="loading" @click="loadCoursewareList">
          {{ loading ? '刷新中...' : '刷新列表' }}
        </AppButton>
      </div>

      <div v-if="errorMsg" class="inline-alert inline-alert--danger">
        {{ errorMsg }}
      </div>

      <div v-if="coursewareList.length" class="classroom-grid">
        <CoursewareCard
          v-for="item in coursewareList"
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
          title="课堂里还没有可继续的课件"
          description="先去导入中心上传本地课件，或者从超星课程导入。完成后会自动出现在这里。"
          action-label="前往导入中心"
          @action="router.push('/imports')"
        />
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listCourseware } from '@/api/courseware'
import CoursewareCard from '@/components/course/CoursewareCard.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { getErrorMessage } from '@/utils'

const router = useRouter()

const loading = ref(false)
const errorMsg = ref('')
const coursewareList = ref([])

const normalizeCoursewareItem = item => ({
  id: item?.id || item?.coursewareId || '',
  name: item?.name || '未命名课件',
  status: String(item?.status || 'UPLOADED').trim().toUpperCase(),
  createdAt: item?.createdAt || item?.updatedAt || '',
  updatedAt: item?.updatedAt || item?.createdAt || '',
  currentTaskStatus: item?.currentTaskStatus || '',
})

const statusRank = status => {
  switch (status) {
    case 'READY':
      return 0
    case 'GENERATING_SCRIPT':
      return 1
    case 'PARSED':
      return 2
    case 'PARSING':
      return 3
    case 'UPLOADED':
      return 4
    case 'FAILED':
      return 5
    default:
      return 6
  }
}

const stats = computed(() => {
  const total = coursewareList.value.length
  const ready = coursewareList.value.filter(item => item.status === 'READY').length
  const failed = coursewareList.value.filter(item => item.status === 'FAILED').length
  const processing = coursewareList.value.filter(item =>
    ['PARSING', 'PARSED', 'GENERATING_SCRIPT', 'UPLOADED'].includes(item.status),
  ).length

  return {
    total,
    ready,
    failed,
    processing,
  }
})

async function loadCoursewareList() {
  loading.value = true
  errorMsg.value = ''

  try {
    const response = await listCourseware()
    const items = Array.isArray(response.data?.items) ? response.data.items : []
    coursewareList.value = items
      .map(normalizeCoursewareItem)
      .sort((left, right) => {
        const rankDiff = statusRank(left.status) - statusRank(right.status)
        if (rankDiff !== 0) {
          return rankDiff
        }

        const leftTime = Date.parse(left.updatedAt || left.createdAt || 0)
        const rightTime = Date.parse(right.updatedAt || right.createdAt || 0)
        return rightTime - leftTime
      })
  } catch (error) {
    errorMsg.value = getErrorMessage(error, '课堂列表加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
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

onMounted(() => {
  loadCoursewareList()
})
</script>

<style scoped>
.classroom-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
}

.classroom-hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.classroom-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 12rem;
}

.summary-label {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.summary-card strong {
  font-size: clamp(2rem, 3vw, 2.6rem);
  line-height: 1;
}

.summary-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

.classroom-section-header {
  align-items: end;
}

.classroom-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.inline-alert {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: var(--radius-md);
  line-height: 1.7;
}

.inline-alert--danger {
  color: #b53f58;
  background: rgba(240, 74, 110, 0.1);
  border: 1px solid rgba(240, 74, 110, 0.14);
}

@media (max-width: 1100px) {
  .classroom-summary,
  .classroom-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .classroom-hero,
  .classroom-section-header {
    flex-direction: column;
    align-items: stretch;
  }

  .classroom-hero__actions > * {
    flex: 1;
  }

  .classroom-summary,
  .classroom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
