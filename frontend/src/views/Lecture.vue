<template>
  <div class="lecture-page">
    <!-- 讲稿内容区域 -->
    <div class="lecture-content">
      <div class="slide-section">
        <div class="slide-header">
          <h2>{{ currentSlide?.title || '加载中...' }}</h2>
          <span class="state-badge" :class="lectureState">{{ stateLabel }}</span>
        </div>
        <div class="slide-body">
          {{ currentSlide?.content || '' }}
        </div>
        <div class="knowledge-tags" v-if="currentSlide?.knowledgePoints?.length">
          <span class="tag" v-for="kp in currentSlide.knowledgePoints" :key="kp">{{ kp }}</span>
        </div>
      </div>

      <!-- 播放控制栏 -->
      <div class="controls">
        <button class="btn btn-control" @click="previousSlide" :disabled="currentPage <= 1">
          ⬅️ 上一页
        </button>

        <div class="center-controls">
          <!-- TTS 语音按钮 -->
          <button class="btn btn-tts" @click="toggleSpeech" :class="{ speaking: isSpeaking }">
            {{ isSpeaking ? '🔊 朗读中' : '🔈 朗读' }}
          </button>

          <!-- 暂停/继续 -->
          <button
            v-if="lectureState === 'playing'"
            class="btn btn-pause"
            @click="pauseLecture"
          >
            ⏸️ 暂停
          </button>
          <button
            v-else-if="lectureState === 'paused'"
            class="btn btn-resume"
            @click="resumeLecture"
          >
            ▶️ 继续
          </button>

          <span class="progress">{{ currentPage }} / {{ totalPages }}</span>
        </div>

        <button class="btn btn-control" @click="nextSlide" :disabled="currentPage >= totalPages">
          下一页 ➡️
        </button>
      </div>

      <!-- 进度条 -->
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
    </div>

    <!-- 问答区域 -->
    <div class="qa-section">
      <h3>💬 学生问答</h3>
      <div class="qa-input">
        <input
          v-model="question"
          type="text"
          placeholder="输入您的问题..."
          :disabled="isAsking"
          @keyup.enter="submitQuestion"
        />
        <button class="btn btn-small" @click="submitQuestion" :disabled="!question.trim() || isAsking">
          {{ isAsking ? '...' : '提问' }}
        </button>
      </div>

      <div class="qa-history" ref="qaHistoryRef">
        <div v-for="qa in qaList" :key="qa.id" class="qa-item">
          <div class="qa-question">Q: {{ qa.question }}</div>
          <div class="qa-answer" v-html="renderMd(qa.answer)"></div>
          <div class="qa-evidence" v-if="qa.evidence?.length">
            <details>
              <summary>📎 参考来源 ({{ qa.evidence.length }})</summary>
              <div v-for="(ev, i) in qa.evidence" :key="i" class="evidence-item">
                <span class="evidence-source">{{ ev.source }}</span>
                {{ ev.text }}
              </div>
            </details>
          </div>
        </div>
        <div v-if="qaList.length === 0" class="qa-empty">暂无问答记录，试试问个问题吧</div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-toast" @click="errorMsg = ''">⚠️ {{ errorMsg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCoursStore } from '@/stores/cours'
import request from '@/utils/request'
import { LECTURE_API, QA_API, SCRIPT_API } from '@/constans/api'
import { LECTURE_STATE } from '@/constans/lecture'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()
const coursStore = useCoursStore()

const coursewareId = route.params.coursewareId

// 讲课状态
const lectureState = ref(LECTURE_STATE.IDLE)
const sessionId = ref(null)
const slides = ref([])
const currentPage = ref(1)
const errorMsg = ref('')

// 问答
const question = ref('')
const isAsking = ref(false)
const qaList = ref([])
const qaHistoryRef = ref(null)

// TTS
const isSpeaking = ref(false)
let speechUtterance = null

// 计算属性
const currentSlide = computed(() => slides.value[currentPage.value - 1])
const totalPages = computed(() => slides.value.length)
const progressPercent = computed(() =>
  totalPages.value > 0 ? Math.round((currentPage.value / totalPages.value) * 100) : 0
)
const stateLabel = computed(() => {
  const labels = { idle: '未开始', playing: '讲课中', paused: '已暂停', finished: '已完成' }
  return labels[lectureState.value] || ''
})

// Markdown 渲染
const renderMd = text => {
  if (!text) return ''
  return marked.parse(text, { breaks: true })
}

// ========== 讲课流程 ==========
const startLecture = async () => {
  try {
    const res = await request.post(LECTURE_API.START, { coursewareId })
    if (res.code === 0) {
      sessionId.value = res.data.sessionId
      lectureState.value = LECTURE_STATE.PLAYING
      // 如果返回了当前 node，定位到对应页
      if (res.data.currentNode?.pageIndex) {
        currentPage.value = res.data.currentNode.pageIndex
      }
    } else {
      errorMsg.value = res.message || '开始讲课失败'
    }
  } catch {
    errorMsg.value = '网络错误，无法开始讲课'
  }
}

const pauseLecture = async () => {
  stopSpeech()
  try {
    await request.post(LECTURE_API.PAUSE(sessionId.value))
  } catch {
    // 即使网络失败也允许本地暂停
  }
  lectureState.value = LECTURE_STATE.PAUSED
  coursStore.currentSession && (coursStore.currentSession.status = 'paused')
}

const resumeLecture = async () => {
  try {
    const res = await request.post(LECTURE_API.RESUME, { sessionId: sessionId.value })
    if (res.code === 0 && res.data?.currentNode?.pageIndex) {
      currentPage.value = res.data.currentNode.pageIndex
    }
  } catch {
    // 网络失败时本地恢复
  }
  lectureState.value = LECTURE_STATE.PLAYING
  coursStore.currentSession && (coursStore.currentSession.status = 'playing')
}

// ========== 翻页 ==========
const previousSlide = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    stopSpeech()
  }
}

const nextSlide = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    stopSpeech()
  } else {
    lectureState.value = LECTURE_STATE.FINISHED
    stopSpeech()
  }
}

// ========== TTS 语音合成 ==========
const toggleSpeech = () => {
  if (isSpeaking.value) {
    stopSpeech()
  } else {
    speakCurrent()
  }
}

const speakCurrent = () => {
  const text = currentSlide.value?.content
  if (!text || !globalThis.speechSynthesis) return

  stopSpeech()
  speechUtterance = new SpeechSynthesisUtterance(text)
  speechUtterance.lang = 'zh-CN'
  speechUtterance.rate = 1
  speechUtterance.onend = () => { isSpeaking.value = false }
  speechUtterance.onerror = () => { isSpeaking.value = false }
  globalThis.speechSynthesis.speak(speechUtterance)
  isSpeaking.value = true
}

const stopSpeech = () => {
  if (globalThis.speechSynthesis) {
    globalThis.speechSynthesis.cancel()
  }
  isSpeaking.value = false
}

// ========== 问答 ==========
const submitQuestion = async () => {
  const q = question.value.trim()
  if (!q || isAsking.value) return

  isAsking.value = true
  const qaItem = { id: Date.now(), question: q, answer: '正在思考...', evidence: [] }
  qaList.value.push(qaItem)
  question.value = ''
  scrollQAToBottom()

  try {
    const res = await request.post(QA_API.ASK_TEXT, {
      sessionId: sessionId.value,
      question: q,
    })
    if (res.code === 0) {
      qaItem.answer = res.data.answer || '暂无答案'
      qaItem.evidence = res.data.evidence || []
    } else {
      qaItem.answer = res.message || '获取答案失败'
    }
  } catch {
    qaItem.answer = '网络错误，请稍后重试'
  } finally {
    isAsking.value = false
    coursStore.addQARecord({ question: q, answer: qaItem.answer })
    scrollQAToBottom()
  }
}

const scrollQAToBottom = () => {
  nextTick(() => {
    if (qaHistoryRef.value) {
      qaHistoryRef.value.scrollTop = qaHistoryRef.value.scrollHeight
    }
  })
}

// ========== 初始化 ==========
const loadSlides = async () => {
  try {
    const res = await request.get(SCRIPT_API.GET(coursewareId))
    if (res.code === 0 && res.data?.segments) {
      slides.value = res.data.segments
    } else {
      errorMsg.value = '讲稿数据为空，请先生成讲稿'
    }
  } catch {
    errorMsg.value = '无法加载讲稿数据'
  }
}

onMounted(async () => {
  await loadSlides()
  if (slides.value.length > 0) {
    await startLecture()
  }
})

onUnmounted(() => {
  stopSpeech()
})
</script>

<style scoped>
.lecture-page {
  display: flex;
  gap: 1.5rem;
  padding: 1.5rem;
  height: calc(100vh - 9rem);
  overflow: hidden;
}

.lecture-content {
  flex: 2;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.slide-section {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}

.slide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.slide-header h2 {
  font-size: var(--font-size-xl);
  color: var(--primary-color);
  margin: 0;
}

.state-badge {
  font-size: var(--font-size-xs);
  padding: 0.25rem 0.75rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
}
.state-badge.playing { background: rgba(82, 196, 26, 0.15); color: #389e0d; }
.state-badge.paused { background: rgba(250, 173, 20, 0.15); color: #d48806; }
.state-badge.finished { background: rgba(102, 126, 234, 0.15); color: var(--primary-color); }
.state-badge.idle { background: var(--bg-secondary); color: var(--text-secondary); }

.slide-body {
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
  color: var(--text-secondary);
  min-height: 10rem;
}

.knowledge-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.knowledge-tags .tag {
  padding: 0.2rem 0.6rem;
  background: rgba(102, 126, 234, 0.1);
  color: var(--primary-color);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}

.controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
  gap: 0.5rem;
}

.center-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.btn-tts {
  font-size: var(--font-size-sm);
  padding: 0.4rem 0.8rem;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
}
.btn-tts.speaking {
  background: rgba(82, 196, 26, 0.15);
  border-color: #52c41a;
  color: #389e0d;
}

.btn-pause, .btn-resume {
  font-size: var(--font-size-sm);
  padding: 0.4rem 0.8rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  transition: all 0.2s;
}

.progress {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.progress-bar {
  height: 3px;
  background: var(--border-color);
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  transition: width 0.3s ease;
}

/* 问答区域 */
.qa-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  padding: 1.5rem;
  overflow: hidden;
}

.qa-section h3 {
  margin: 0 0 1rem 0;
  color: var(--primary-color);
}

.qa-input {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.qa-input input {
  flex: 1;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color 0.2s;
}
.qa-input input:focus {
  border-color: var(--primary-color);
}

.qa-history {
  flex: 1;
  overflow-y: auto;
}

.qa-item {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.qa-question {
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: 0.5rem;
  font-size: var(--font-size-sm);
}

.qa-answer {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
.qa-answer :deep(p) { margin: 0.25rem 0; }
.qa-answer :deep(code) {
  background: rgba(0,0,0,0.06);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.85em;
}
.qa-answer :deep(pre) {
  background: #f6f8fa;
  padding: 0.75rem;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-size: 0.85em;
}

.qa-evidence {
  margin-top: 0.5rem;
  font-size: var(--font-size-xs);
}
.qa-evidence summary {
  cursor: pointer;
  color: var(--text-secondary);
}
.evidence-item {
  margin-top: 0.25rem;
  padding: 0.4rem;
  background: white;
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary-color);
}
.evidence-source {
  font-weight: 600;
  color: var(--primary-color);
  margin-right: 0.5rem;
}

.qa-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 2rem 0;
  font-size: var(--font-size-sm);
}

.error-toast {
  position: fixed;
  bottom: 5rem;
  left: 50%;
  transform: translateX(-50%);
  padding: 0.75rem 1.5rem;
  background: var(--error-color);
  color: white;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  cursor: pointer;
  z-index: 100;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .lecture-page {
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    height: auto;
    overflow-y: auto;
  }

  .lecture-content { flex: none; min-height: 50vh; }
  .qa-section { flex: none; min-height: 40vh; }

  .slide-section { padding: 1rem; }
  .slide-header h2 { font-size: var(--font-size-lg); }
  .controls { padding: 0.75rem 1rem; flex-wrap: wrap; }
  .center-controls { order: -1; width: 100%; justify-content: center; margin-bottom: 0.5rem; }
}

@media (max-width: 480px) {
  .lecture-page { padding: 0.5rem; gap: 0.5rem; }
  .slide-body { min-height: 8rem; font-size: var(--font-size-sm); }
  .qa-section { padding: 1rem; }
  .btn { padding: 0.5rem 1rem; font-size: var(--font-size-sm); }
}
</style>
