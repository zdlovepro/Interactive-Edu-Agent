<template>
  <div class="courses-page">
    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">课程工作台</span>
          <h1 class="page-title">课程列表</h1>
          <p class="page-description">
            统一查看上传的课件、超星课程导入任务与后续讲稿入口，适合课前准备和课后继续处理。
          </p>
        </div>
      </div>

      <AppCard tone="glass" class="toolbar-card">
        <div class="toolbar">
          <div class="toolbar-search">
            <label for="course-search" class="visually-hidden">搜索课程</label>
            <input
              id="course-search"
              v-model.trim="keyword"
              class="app-input"
              type="text"
              placeholder="搜索课程名称"
            />
          </div>
          <div class="toolbar-actions">
            <AppButton variant="secondary" @click="router.push('/course-resource-import')">
              从超星课程导入
            </AppButton>
            <AppButton @click="router.push('/upload')">上传课件</AppButton>
          </div>
        </div>
      </AppCard>
    </section>

    <section class="page-shell page-section">
      <div class="stats-grid">
        <AppCard v-for="card in statsCards" :key="card.label" tone="subtle" class="stats-card">
          <span class="stats-label">{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.description }}</p>
        </AppCard>
      </div>
    </section>

    <section class="page-shell page-section">
      <div v-if="errorMessage" class="inline-error">
        <span>{{ errorMessage }}</span>
        <button type="button" @click="errorMessage = ''">关闭</button>
      </div>

      <div v-if="loading" class="course-grid">
        <AppCard v-for="index in 3" :key="index" class="skeleton-card">
          <div class="skeleton-line skeleton-line--lg"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line"></div>
        </AppCard>
      </div>

      <div v-else-if="filteredCourses.length" class="course-grid">
        <CoursewareCard
          v-for="item in filteredCourses"
          :key="item.id"
          :courseware="item"
          @view-script="openScript"
          @enter-lecture="enterLecture"
        />
      </div>

      <AppCard v-else tone="glass">
        <EmptyState
          title="还没有课程资源"
          description="你可以先上传本地课件，也可以直接从超星课程页导入课件资源。"
          action-label="从超星课程导入"
          @action="router.push('/course-resource-import')"
        />
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CoursewareCard from '@/components/course/CoursewareCard.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { listCourseware } from '@/api/courseware'
import { getErrorMessage } from '@/utils'

const router = useRouter()

const keyword = ref('')
const loading = ref(false)
const errorMessage = ref('')
const coursewareList = ref([])

const filteredCourses = computed(() => {
  const search = keyword.value.toLowerCase()
  if (!search) {
    return coursewareList.value
  }

  return coursewareList.value.filter(item => item.name?.toLowerCase().includes(search))
})

const statsCards = computed(() => {
  const total = coursewareList.value.length
  const ready = coursewareList.value.filter(item => item.status === 'READY').length
  const processing = coursewareList.value.filter(
    item => item.status === 'GENERATING_SCRIPT' || item.status === 'PARSING' || item.status === 'PARSED',
  ).length
  const failed = coursewareList.value.filter(item => item.status === 'FAILED').length

  return [
    { label: '课程总数', value: total, description: '当前可继续追踪的课件与课程资源。' },
    { label: '已就绪', value: ready, description: '可以直接查看讲稿或进入讲课页。' },
    { label: '处理中', value: processing, description: '正在解析课件或生成讲稿的课程。' },
    { label: '失败', value: failed, description: '需要重新上传或重新处理的课程。' },
  ]
})

function normalizeCourseware(item) {
  return {
    id: item?.id || item?.coursewareId || '',
    name: item?.name || '未命名课程',
    status: item?.status || 'UPLOADED',
    createdAt: item?.createdAt || '',
    updatedAt: item?.updatedAt || '',
    currentTaskStatus: item?.currentTaskStatus || '',
  }
}

async function loadCoursewareList() {
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await listCourseware()
    coursewareList.value = Array.isArray(response.data?.items)
      ? response.data.items.map(normalizeCourseware)
      : []
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '加载课程列表失败，请稍后重试。')
  } finally {
    loading.value = false
  }
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
.toolbar-card {
  padding: 1rem 1.1rem;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.toolbar-search {
  flex: 1;
  max-width: 420px;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.stats-grid,
.course-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.stats-card strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 2rem;
}

.stats-label {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.stats-card p {
  margin: 0.55rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.inline-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
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

.skeleton-card {
  min-height: 14rem;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.skeleton-line {
  width: 100%;
  height: 0.95rem;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    rgba(229, 232, 246, 0.8),
    rgba(242, 244, 255, 1),
    rgba(229, 232, 246, 0.8)
  );
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite linear;
}

.skeleton-line--lg {
  width: 70%;
  height: 1.35rem;
}

@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}

@media (max-width: 1080px) {
  .stats-grid,
  .course-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-search {
    max-width: none;
  }

  .toolbar-actions {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .stats-grid,
  .course-grid {
    grid-template-columns: 1fr;
  }
}
</style>
