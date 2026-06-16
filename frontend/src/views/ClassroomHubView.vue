<template>
  <div class="classroom-page">
    <section class="page-shell page-section classroom-hero">
      <div>
        <span class="eyebrow">{{ authStore.isTeacher ? 'Teacher Workspace' : 'Student Workspace' }}</span>
        <h1 class="page-title">{{ heroTitle }}</h1>
        <p class="page-description">
          {{ heroDescription }}
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
          <span class="summary-label">我的课件</span>
          <strong>{{ ownedCoursewareList.length }}</strong>
          <p>当前账号自己上传并可继续编辑、生成讲稿或渲染视频的课件资源。</p>
        </AppCard>

        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">可直接上课</span>
          <strong>{{ readyCount }}</strong>
          <p>状态为 `READY` 的课件可以直接进入讲稿页或课堂演示页。</p>
        </AppCard>

        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">处理中</span>
          <strong>{{ processingCount }}</strong>
          <p>仍在解析、生成讲稿或等待进一步处理的课件会集中显示在这里。</p>
        </AppCard>

        <AppCard class="summary-card" tone="glass">
          <span class="summary-label">{{ authStore.isTeacher ? '共享说明' : '已连接课程' }}</span>
          <strong>{{ authStore.isTeacher ? '课程号分享' : connectedCourseCodes.length }}</strong>
          <p>
            {{ authStore.isTeacher ? '教师可在资源详情页设置课程号，让学生通过课程号访问该课件。' : sharedSummaryText }}
          </p>
        </AppCard>
      </div>
    </section>

    <section v-if="authStore.isStudent" class="page-shell page-section">
      <AppCard class="shared-access-card" tone="accent">
        <div class="shared-access-card__copy">
          <span class="eyebrow">课程号访问</span>
          <h2>连接教师共享课件</h2>
          <p>
            输入教师发布的课程号后，系统会把对应课件资源加入当前课堂视图。
            你可以连续连接多门课程，系统会分别拉取每个课程号下的共享课件。
          </p>
        </div>

        <div class="shared-access-card__form">
          <input
            v-model.trim="sharedCodeInput"
            class="app-input"
            type="text"
            placeholder="例如：ML-2026-A"
            @keyup.enter="applySharedCourseCode"
          />
          <div class="shared-access-card__actions">
            <AppButton :disabled="!sharedCodeInput" @click="applySharedCourseCode">连接课程号</AppButton>
            <AppButton
              variant="secondary"
              :disabled="!connectedCourseCodes.length"
              @click="clearAllSharedCourseCodes"
            >
              清空全部
            </AppButton>
          </div>
          <p class="shared-access-card__hint">
            {{ sharedAccessHint }}
          </p>

          <div v-if="connectedCourseCodes.length" class="connected-course-list">
            <div
              v-for="courseCode in connectedCourseCodes"
              :key="courseCode"
              class="connected-course-item"
              :class="{ active: courseCode === authStore.sharedCourseCode }"
            >
              <div class="connected-course-item__meta">
                <strong>{{ courseCode }}</strong>
                <span>{{ courseCode === authStore.sharedCourseCode ? '当前生效' : '已连接' }}</span>
              </div>
              <div class="connected-course-item__actions">
                <AppButton
                  variant="secondary"
                  size="sm"
                  :disabled="courseCode === authStore.sharedCourseCode"
                  @click="setActiveSharedCourseCode(courseCode)"
                >
                  设为当前
                </AppButton>
                <button type="button" class="connected-course-item__remove" @click="removeSharedCourseCode(courseCode)">
                  移除
                </button>
              </div>
            </div>
          </div>
        </div>
      </AppCard>
    </section>

    <section class="page-shell page-section">
      <div class="section-header classroom-section-header">
        <div>
          <span class="eyebrow">{{ authStore.isTeacher ? '我的课程资源' : '我的课件' }}</span>
          <h2 class="page-title section-title">{{ authStore.isTeacher ? '教师资源工作台' : '继续你的课件与课堂流程' }}</h2>
        </div>

        <AppButton variant="secondary" :disabled="loadingOwned" @click="loadOwnedCourseware">
          {{ loadingOwned ? '刷新中...' : '刷新列表' }}
        </AppButton>
      </div>

      <div v-if="errorMsg" class="inline-alert inline-alert--danger">
        {{ errorMsg }}
      </div>

      <div v-if="ownedCoursewareList.length" class="classroom-grid">
        <CoursewareCard
          v-for="item in ownedCoursewareList"
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
          title="当前还没有自己的课件"
          description="先去导入中心上传或导入课件，处理完成后会自动回到这里。"
          action-label="前往导入中心"
          @action="router.push('/imports')"
        />
      </AppCard>
    </section>

    <section v-if="authStore.isStudent" class="page-shell page-section">
      <div class="section-header classroom-section-header">
        <div>
          <span class="eyebrow">共享课件</span>
          <h2 class="page-title section-title">通过课程号加入的教师课件</h2>
        </div>

        <AppButton
          variant="secondary"
          :disabled="loadingShared || !connectedCourseCodes.length"
          @click="loadSharedCourseware"
        >
          {{ loadingShared ? '刷新中...' : '刷新共享列表' }}
        </AppButton>
      </div>

      <div v-if="connectedCourseCodes.length && sharedCoursewareList.length" class="classroom-grid">
        <CoursewareCard
          v-for="item in sharedCoursewareList"
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
          :title="connectedCourseCodes.length ? '当前课程列表下暂无可访问共享课件' : '尚未连接教师课程号'"
          :description="connectedCourseCodes.length
            ? '请确认教师已为目标课件设置这些课程号之一，或稍后再刷新。'
            : '输入教师提供的课程号后，这里会展示对应的共享课件。'"
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
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils'

const router = useRouter()
const authStore = useAuthStore()

const loadingOwned = ref(false)
const loadingShared = ref(false)
const errorMsg = ref('')
const ownedCoursewareList = ref([])
const sharedCoursewareList = ref([])
const sharedCodeInput = ref('')

const connectedCourseCodes = computed(() => authStore.sharedCourseCodes)

const heroTitle = computed(() =>
  authStore.isTeacher ? '管理你的课程资源与发布课程号' : '继续你的课件学习与互动课堂',
)

const heroDescription = computed(() =>
  authStore.isTeacher
    ? '教师侧聚焦于上传课件、生成讲稿、渲染讲解视频，以及为课件设置课程号，方便学生通过课程号获取共享资源。'
    : '学生侧可以继续自己的课件流程，也可以通过教师提供的课程号加入共享课件，随后进入完整互动课堂。',
)

const allCourseware = computed(() => [...ownedCoursewareList.value, ...sharedCoursewareList.value])

const readyCount = computed(() =>
  allCourseware.value.filter(item => String(item.status || '').toUpperCase() === 'READY').length,
)

const processingCount = computed(() =>
  allCourseware.value.filter(item =>
    ['UPLOADED', 'PARSING', 'PARSED', 'GENERATING_SCRIPT'].includes(String(item.status || '').toUpperCase()),
  ).length,
)

const sharedSummaryText = computed(() =>
  connectedCourseCodes.value.length
    ? `已连接 ${connectedCourseCodes.value.length} 门课程，当前汇总了 ${sharedCoursewareList.value.length} 份共享课件。`
    : '输入教师提供的课程号后，这里会展示可访问的共享课件。',
)

const sharedAccessHint = computed(() =>
  connectedCourseCodes.value.length
    ? `当前生效课程号：${authStore.sharedCourseCode || '未选择'}。进入某份共享课件时会自动切换到对应课程号。`
    : '尚未连接课程号，连接后这里会保留你的课程列表。',
)

function normalizeCoursewareItem(item, linkedCourseCode = '') {
  return {
    id: item?.id || item?.coursewareId || '',
    name: item?.name || '未命名课件',
    status: String(item?.status || 'UPLOADED').trim().toUpperCase(),
    createdAt: item?.createdAt || item?.updatedAt || '',
    updatedAt: item?.updatedAt || item?.createdAt || '',
    currentTaskStatus: item?.currentTaskStatus || '',
    courseCode: item?.courseCode || '',
    accessMode: String(item?.accessMode || 'OWNED').trim().toUpperCase(),
    linkedCourseCode: linkedCourseCode || item?.courseCode || '',
  }
}

function resolveCoursewareTimestamp(item) {
  const rawValue = item?.updatedAt || item?.createdAt || ''
  const timestamp = Date.parse(rawValue)
  return Number.isFinite(timestamp) ? timestamp : 0
}

async function loadOwnedCourseware() {
  loadingOwned.value = true
  errorMsg.value = ''

  try {
    const response = await listCourseware({ scope: 'owned', pageSize: 50 })
    const items = Array.isArray(response.data?.items) ? response.data.items : []
    ownedCoursewareList.value = items.map(normalizeCoursewareItem)
  } catch (error) {
    errorMsg.value = getErrorMessage(error, '课件列表加载失败，请稍后重试。')
  } finally {
    loadingOwned.value = false
  }
}

async function loadSharedCourseware() {
  if (!connectedCourseCodes.value.length) {
    sharedCoursewareList.value = []
    return
  }

  loadingShared.value = true
  errorMsg.value = ''

  try {
    const settledResults = await Promise.allSettled(
      connectedCourseCodes.value.map(courseCode =>
        listCourseware(
          { scope: 'shared', pageSize: 50 },
          {
            headers: {
              'X-Course-Code': courseCode,
            },
          },
        ).then(response => ({
          courseCode,
          items: Array.isArray(response.data?.items) ? response.data.items : [],
        })),
      ),
    )

    const mergedCourseware = []
    let hasLoadFailure = false

    for (const result of settledResults) {
      if (result.status !== 'fulfilled') {
        hasLoadFailure = true
        continue
      }

      for (const item of result.value.items) {
        const normalizedItem = normalizeCoursewareItem(item, result.value.courseCode)
        mergedCourseware.push(normalizedItem)
      }
    }

    sharedCoursewareList.value = mergedCourseware.sort(
      (left, right) => resolveCoursewareTimestamp(right) - resolveCoursewareTimestamp(left),
    )

    if (hasLoadFailure && !sharedCoursewareList.value.length) {
      errorMsg.value = '部分共享课程加载失败，请稍后重试。'
    }
  } catch (error) {
    errorMsg.value = getErrorMessage(error, '共享课件加载失败，请稍后重试。')
  } finally {
    loadingShared.value = false
  }
}

async function applySharedCourseCode() {
  const normalized = authStore.setCourseCode(sharedCodeInput.value)
  sharedCodeInput.value = ''
  if (!normalized) {
    sharedCoursewareList.value = []
    return
  }
  await loadSharedCourseware()
}

async function clearAllSharedCourseCodes() {
  authStore.clearCourseCode()
  sharedCodeInput.value = ''
  sharedCoursewareList.value = []
}

function setActiveSharedCourseCode(courseCode) {
  authStore.setActiveCourseCode(courseCode)
}

async function removeSharedCourseCode(courseCode) {
  authStore.removeCourseCode(courseCode)
  if (!connectedCourseCodes.value.length) {
    sharedCoursewareList.value = []
    return
  }
  await loadSharedCourseware()
}

function buildSharedCoursewareRoute(name, courseware) {
  const nextCourseCode = courseware.accessMode === 'SHARED'
    ? courseware.linkedCourseCode || courseware.courseCode || ''
    : ''

  if (nextCourseCode) {
    authStore.setActiveCourseCode(nextCourseCode)
  }

  return {
    name,
    params: { coursewareId: courseware.id },
    query: nextCourseCode ? { courseCode: nextCourseCode } : undefined,
  }
}

function openDetail(courseware) {
  router.push(buildSharedCoursewareRoute('ResourceDetail', courseware))
}

function openScript(courseware) {
  router.push(buildSharedCoursewareRoute('Script', courseware))
}

function enterLecture(courseware) {
  router.push(buildSharedCoursewareRoute('Lecture', courseware))
}

onMounted(async () => {
  authStore.restore()
  await loadOwnedCourseware()
  if (authStore.isStudent && connectedCourseCodes.value.length) {
    await loadSharedCourseware()
  }
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

.shared-access-card {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 1.25rem;
  align-items: center;
}

.shared-access-card__copy h2 {
  margin: 0.4rem 0 0.7rem;
  font-size: 1.8rem;
}

.shared-access-card__copy p,
.shared-access-card__hint {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.shared-access-card__form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1.1rem;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(126, 136, 181, 0.12);
}

.shared-access-card__actions {
  display: flex;
  gap: 0.75rem;
}

.shared-access-card__actions > * {
  flex: 1;
}

.connected-course-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.connected-course-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(126, 136, 181, 0.12);
}

.connected-course-item.active {
  border-color: rgba(14, 90, 224, 0.18);
  box-shadow: inset 0 0 0 1px rgba(14, 90, 224, 0.08);
}

.connected-course-item__meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.connected-course-item__meta strong {
  font-size: 1rem;
}

.connected-course-item__meta span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.connected-course-item__actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.connected-course-item__remove {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
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
  .classroom-grid,
  .shared-access-card {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .classroom-hero,
  .classroom-section-header,
  .shared-access-card {
    flex-direction: column;
    align-items: stretch;
    grid-template-columns: 1fr;
  }

  .classroom-hero__actions > * {
    flex: 1;
  }

  .shared-access-card__actions {
    flex-direction: column;
  }

  .connected-course-item,
  .connected-course-item__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .classroom-summary,
  .classroom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
