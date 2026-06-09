<template>
  <div class="url-import-page">
    <section class="page-shell page-section">
      <div class="section-header">
        <div>
          <span class="eyebrow">实验功能</span>
          <h1 class="page-title">普通 URL 导入</h1>
          <p class="page-description">
            适合直接指向 PDF、PPTX 或图片资源的链接。若提交的是网页地址，任务可能停留在
            WAITING_CRAWLER，表示需要后续 crawler worker 接管。
          </p>
        </div>
        <AppButton variant="secondary" @click="router.push('/imports')">返回导入中心</AppButton>
      </div>
    </section>

    <section class="page-shell page-section">
      <AppCard class="url-import-card" tone="accent">
        <form class="url-import-form" @submit.prevent="handleUrlImport">
          <div class="field-block">
            <label class="field-label" for="url-import-input">资源 URL</label>
            <input
              id="url-import-input"
              v-model.trim="importUrl"
              class="app-input"
              type="url"
              placeholder="https://example.com/courseware.pdf"
              :disabled="urlImportLoading"
            />
          </div>

          <div class="field-block">
            <label class="field-label" for="url-import-name">资源名称</label>
            <input
              id="url-import-name"
              v-model.trim="importName"
              class="app-input"
              type="text"
              placeholder="可选，例如：机器学习导论"
              :disabled="urlImportLoading"
            />
          </div>

          <div class="form-actions">
            <AppButton type="submit" :disabled="urlImportDisabled">
              {{ urlImportLoading ? '提交中...' : '创建 URL 导入任务' }}
            </AppButton>
            <AppButton variant="secondary" @click="router.push('/resources')">去资源库</AppButton>
          </div>
        </form>

        <div v-if="urlTask" class="url-task-panel">
          <div class="url-task-header">
            <div>
              <span class="eyebrow">任务状态</span>
              <h2>{{ urlTask.status }}</h2>
              <p>{{ taskMessage }}</p>
            </div>
            <strong>{{ urlTask.progress || 0 }}%</strong>
          </div>

          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${urlTask.progress || 0}%` }"></div>
          </div>

          <div class="url-steps">
            <span
              v-for="step in urlImportSteps"
              :key="step.key"
              :class="{ active: step.key === activeUrlStep }"
            >
              {{ step.label }}
            </span>
          </div>
        </div>

        <div v-if="errorMessage" class="inline-error">
          <span>{{ errorMessage }}</span>
          <button type="button" @click="errorMessage = ''">关闭</button>
        </div>
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { getUrlImportTask, importCoursewareFromUrl } from '@/api/courseware'
import { getErrorMessage } from '@/utils'

const router = useRouter()

const importUrl = ref('')
const importName = ref('')
const urlTask = ref(null)
const urlImportLoading = ref(false)
const errorMessage = ref('')

let urlTaskPollTimer = null

const urlImportSteps = [
  { key: 'QUEUED', label: '排队' },
  { key: 'FETCHING', label: '抓取' },
  { key: 'WAITING_CRAWLER', label: '等待 worker' },
  { key: 'DOWNLOADING', label: '下载' },
  { key: 'PARSING', label: '解析' },
]

const urlImportDisabled = computed(() => urlImportLoading.value || !importUrl.value)
const activeUrlStep = computed(() => urlTask.value?.stage || urlTask.value?.status || 'QUEUED')

const taskMessage = computed(() => {
  if (!urlTask.value) {
    return ''
  }
  if (urlTask.value.status === 'WAITING_CRAWLER') {
    return '任务已创建，正在等待 crawler worker 接管。若当前环境未部署 worker，这里会持续等待。'
  }
  return urlTask.value.message || '任务正在处理，请稍候。'
})

function stopUrlTaskPolling() {
  if (urlTaskPollTimer) {
    window.clearInterval(urlTaskPollTimer)
    urlTaskPollTimer = null
  }
}

function pollUrlImportTask(taskId) {
  stopUrlTaskPolling()
  urlTaskPollTimer = window.setInterval(async () => {
    try {
      const response = await getUrlImportTask(taskId)
      urlTask.value = response.data

      if (['SUCCESS', 'FAILED', 'CANCELLED'].includes(String(urlTask.value?.status || '').toUpperCase())) {
        stopUrlTaskPolling()
      }
    } catch (error) {
      stopUrlTaskPolling()
      errorMessage.value = getErrorMessage(error, 'URL 导入任务状态查询失败，请稍后重试。')
    }
  }, 2500)
}

async function handleUrlImport() {
  if (urlImportDisabled.value) {
    return
  }

  errorMessage.value = ''
  urlImportLoading.value = true

  try {
    const response = await importCoursewareFromUrl({
      url: importUrl.value,
      name: importName.value || undefined,
    })
    urlTask.value = response.data
    if (urlTask.value?.taskId) {
      pollUrlImportTask(urlTask.value.taskId)
    }
  } catch (error) {
    errorMessage.value = getErrorMessage(error, 'URL 导入失败，请检查链接后重试。')
  } finally {
    urlImportLoading.value = false
  }
}

onUnmounted(() => {
  stopUrlTaskPolling()
})
</script>

<style scoped>
.url-import-card,
.url-import-form,
.url-task-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.url-import-form {
  padding: 1rem;
  border: 1px solid rgba(105, 116, 154, 0.14);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.76);
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
}

.url-task-panel {
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: rgba(248, 250, 255, 0.88);
}

.url-task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.url-task-header h2 {
  margin: 0.35rem 0 0;
}

.url-task-header p {
  margin: 0.55rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.url-task-header strong {
  font-size: 2rem;
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

.url-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.5rem;
}

.url-steps span {
  min-height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: rgba(123, 133, 159, 0.1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.url-steps span.active {
  color: #ffffff;
  background: #3f8cff;
}

.inline-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
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

@media (max-width: 700px) {
  .url-steps {
    grid-template-columns: 1fr;
  }

  .url-task-header,
  .form-actions {
    flex-direction: column;
  }
}
</style>

