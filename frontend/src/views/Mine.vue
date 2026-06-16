<template>
  <div class="profile-page">
    <section class="page-shell page-section">
      <div class="profile-hero">
        <div class="profile-copy">
          <span class="eyebrow">个人中心</span>
          <h1 class="page-title">{{ authStore.isTeacher ? '教师工作台' : '学生工作台' }}</h1>
          <p class="page-description">
            {{ roleDescription }}
          </p>
        </div>
        <AppButton size="lg" @click="router.push('/classroom')">进入课堂资源页</AppButton>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="summary-grid">
        <AppCard tone="glass" class="summary-card">
          <span>当前身份</span>
          <strong>{{ authStore.isTeacher ? '教师' : '学生' }}</strong>
          <p>{{ authStore.displayName }}（{{ authStore.user?.username }}）</p>
        </AppCard>

        <AppCard tone="glass" class="summary-card">
          <span>我的课件</span>
          <strong>{{ ownCourseware.length }}</strong>
          <p>当前账号下自己上传或导入的课件资源数量。</p>
        </AppCard>

        <AppCard tone="glass" class="summary-card">
          <span>{{ authStore.isTeacher ? '课程共享' : '已连接课程' }}</span>
          <strong>{{ courseCodeStatusText }}</strong>
          <p>{{ courseCodeHint }}</p>
        </AppCard>

        <AppCard tone="glass" class="summary-card">
          <span>超星授权</span>
          <strong>{{ authStatusText }}</strong>
          <p>{{ authHint }}</p>
          <AppButton variant="secondary" size="sm" @click="router.push('/imports/chaoxing')">
            管理授权
          </AppButton>
        </AppCard>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="section-header classroom-section-header">
        <div>
          <span class="eyebrow">快速操作</span>
          <h2 class="page-title section-title">{{ authStore.isTeacher ? '继续备课与发布' : '继续学习与互动课堂' }}</h2>
        </div>
      </div>

      <div class="quick-grid">
        <AppCard tone="accent" class="quick-card">
          <h3>上传或导入课件</h3>
          <p>从本地上传、超星导入或 URL 导入开始，进入完整处理链路。</p>
          <AppButton @click="router.push('/imports')">打开导入中心</AppButton>
        </AppCard>

        <AppCard tone="glass" class="quick-card">
          <h3>{{ authStore.isTeacher ? '设置课程号' : '管理已连接课程' }}</h3>
          <p>{{ authStore.isTeacher ? '在资源详情页为课件设置课程号，方便学生按课程号访问。' : '学生可以连接多门课程，并在课堂资源页查看所有共享课件。' }}</p>
          <AppButton variant="secondary" @click="router.push('/classroom')">
            打开课堂资源页
          </AppButton>
        </AppCard>

        <AppCard tone="glass" class="quick-card">
          <h3>我的课程资源</h3>
          <p>集中查看你当前可继续处理、演示或进入课堂的课件。</p>
          <AppButton variant="secondary" @click="router.push('/classroom')">
            查看课件列表
          </AppButton>
        </AppCard>
      </div>
    </section>

    <section v-if="authStore.isStudent" class="page-shell page-section">
      <div class="section-header classroom-section-header">
        <div>
          <span class="eyebrow">已连接课程</span>
          <h2 class="page-title section-title">你的课程号列表</h2>
        </div>

        <AppButton variant="secondary" @click="router.push('/classroom')">
          去连接更多课程
        </AppButton>
      </div>

      <div v-if="connectedCourseCodes.length" class="connected-course-grid">
        <AppCard
          v-for="courseCode in connectedCourseCodes"
          :key="courseCode"
          tone="glass"
          class="connected-course-card"
          :class="{ active: courseCode === authStore.sharedCourseCode }"
        >
          <div class="connected-course-card__header">
            <div>
              <span>课程号</span>
              <strong>{{ courseCode }}</strong>
            </div>
            <span class="connected-course-card__status">
              {{ courseCode === authStore.sharedCourseCode ? '当前生效' : '已连接' }}
            </span>
          </div>

          <div class="connected-course-card__actions">
            <AppButton
              variant="secondary"
              :disabled="courseCode === authStore.sharedCourseCode"
              @click="setActiveCourseCode(courseCode)"
            >
              设为当前
            </AppButton>
            <AppButton variant="secondary" @click="removeCourseCode(courseCode)">
              移除
            </AppButton>
          </div>
        </AppCard>
      </div>

      <AppCard v-else tone="glass">
        <EmptyState
          title="还没有连接任何课程号"
          description="前往课堂资源页输入教师提供的课程号后，这里会显示你已加入的课程列表。"
          action-label="前往课堂资源页"
          @action="router.push('/classroom')"
        />
      </AppCard>
    </section>

    <section class="page-shell page-section">
      <div class="section-header classroom-section-header">
        <div>
          <span class="eyebrow">最近课件</span>
          <h2 class="page-title section-title">查看自己的课程资源</h2>
        </div>

        <AppButton variant="secondary" :disabled="loading" @click="loadOwnCourseware">
          {{ loading ? '刷新中...' : '刷新列表' }}
        </AppButton>
      </div>

      <div v-if="errorMessage" class="inline-error">
        <span>{{ errorMessage }}</span>
        <button type="button" @click="errorMessage = ''">关闭</button>
      </div>

      <div v-if="ownCourseware.length" class="course-grid">
        <CoursewareCard
          v-for="item in ownCourseware"
          :key="item.id"
          :courseware="item"
          @view-detail="openDetail"
          @view-script="openScript"
          @enter-lecture="openLecture"
          @retry="openDetail"
        />
      </div>

      <AppCard v-else tone="glass">
        <EmptyState
          title="还没有自己的课件资源"
          description="完成一次上传或导入之后，这里会显示当前账号下的课程资源。"
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
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import CoursewareCard from '@/components/course/CoursewareCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { listCourseware } from '@/api/courseware'
import { useAuthStore } from '@/stores/auth'
import { useChaoxingAuthStore } from '@/stores/chaoxingAuth'
import { getErrorMessage } from '@/utils'

const router = useRouter()
const authStore = useAuthStore()
const chaoxingAuthStore = useChaoxingAuthStore()

const ownCourseware = ref([])
const loading = ref(false)
const errorMessage = ref('')

const roleDescription = computed(() =>
  authStore.isTeacher
    ? '教师侧主要负责管理自己的课件、生成讲稿和讲解视频，并为可共享课件设置课程号。'
    : '学生侧在保留自己课件流程的同时，可以通过教师提供的课程号加入共享课件并进入互动课堂。',
)
const connectedCourseCodes = computed(() => authStore.sharedCourseCodes)

const courseCodeStatusText = computed(() => {
  if (authStore.isTeacher) {
    return '按课件设置'
  }
  return `${connectedCourseCodes.value.length} 门`
})

const courseCodeHint = computed(() =>
  authStore.isTeacher
    ? '教师可在课件详情页按课件设置课程号。'
    : connectedCourseCodes.value.length
      ? `当前共连接 ${connectedCourseCodes.value.length} 门课程，当前生效课程号为 ${authStore.sharedCourseCode || '未选择'}。`
      : '暂未连接教师课程号，可在课堂资源页输入后访问共享课件。',
)

const authStatusText = computed(() => {
  if (chaoxingAuthStore.isAuthorized) {
    return '已授权'
  }
  if (chaoxingAuthStore.sessionId) {
    return chaoxingAuthStore.status || '未完成'
  }
  return '未授权'
})

const authHint = computed(() => {
  if (chaoxingAuthStore.isAuthorized) {
    return '当前只保存本次授权会话 ID，不会在前端保存完整 Cookie。'
  }
  return '需要从超星导入课程时，请先完成扫码授权。'
})

function normalizeCoursewareItem(item) {
  return {
    id: item?.id || item?.coursewareId || '',
    name: item?.name || '未命名课件',
    status: String(item?.status || 'UPLOADED').trim().toUpperCase(),
    createdAt: item?.createdAt || item?.updatedAt || '',
    updatedAt: item?.updatedAt || item?.createdAt || '',
    currentTaskStatus: item?.currentTaskStatus || '',
    courseCode: item?.courseCode || '',
    accessMode: String(item?.accessMode || 'OWNED').trim().toUpperCase(),
  }
}

async function loadOwnCourseware() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listCourseware({ scope: 'owned', pageSize: 20 })
    ownCourseware.value = Array.isArray(response.data?.items)
      ? response.data.items.map(normalizeCoursewareItem)
      : []
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '加载个人课件失败，请稍后重试。')
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

function openLecture(courseware) {
  router.push({ name: 'Lecture', params: { coursewareId: courseware.id } })
}

function setActiveCourseCode(courseCode) {
  authStore.setActiveCourseCode(courseCode)
}

function removeCourseCode(courseCode) {
  authStore.removeCourseCode(courseCode)
}

onMounted(async () => {
  authStore.restore()
  chaoxingAuthStore.restoreFromLocalStorage()
  await loadOwnCourseware()
})
</script>

<style scoped>
.profile-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  padding: 2rem;
  border: 1px solid rgba(123, 134, 182, 0.12);
  border-radius: calc(var(--radius-xl) + 0.15rem);
  background:
    radial-gradient(circle at top left, rgba(100, 112, 255, 0.18), transparent 34%),
    rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow-md);
}

.summary-grid,
.quick-grid,
.course-grid,
.connected-course-grid {
  display: grid;
  gap: 1rem;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.quick-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.course-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.connected-course-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-card,
.quick-card,
.connected-course-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.summary-card span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.summary-card strong {
  font-size: 1.45rem;
}

.summary-card p,
.quick-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.connected-course-card {
  justify-content: space-between;
}

.connected-course-card.active {
  border-color: rgba(14, 90, 224, 0.18);
  box-shadow: inset 0 0 0 1px rgba(14, 90, 224, 0.08);
}

.connected-course-card__header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.connected-course-card__header span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.connected-course-card__header strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 1.3rem;
}

.connected-course-card__status {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  color: var(--primary-color);
  background: rgba(14, 90, 224, 0.08);
  font-weight: 700;
}

.connected-course-card__actions {
  display: flex;
  gap: 0.75rem;
}

.summary-card .app-button,
.quick-card .app-button {
  margin-top: auto;
}

.quick-card h3 {
  margin: 0;
  font-size: 1.15rem;
}

.classroom-section-header {
  align-items: end;
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

@media (max-width: 1080px) {
  .summary-grid,
  .quick-grid,
  .course-grid,
  .connected-course-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .profile-hero {
    align-items: flex-start;
    flex-direction: column;
    padding: 1.35rem;
  }
}

@media (max-width: 640px) {
  .summary-grid,
  .quick-grid,
  .course-grid,
  .connected-course-grid {
    grid-template-columns: 1fr;
  }

  .inline-error {
    flex-direction: column;
    align-items: flex-start;
  }

  .connected-course-card__header,
  .connected-course-card__actions {
    flex-direction: column;
  }
}
</style>
