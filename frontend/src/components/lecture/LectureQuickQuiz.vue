<template>
  <AppCard class="quiz-card" tone="glass">
    <div class="quiz-header">
      <div>
        <span class="quiz-label">课堂增强</span>
        <h2>随堂小测</h2>
        <p>
          基于当前整份课件自动生成题目，适合答辩时展示“讲完即可测、问完即可反馈”的闭环能力。
        </p>
      </div>

      <div class="quiz-actions">
        <AppButton v-if="!submitted" :disabled="!canSubmit" @click="submitQuiz">提交测验</AppButton>
        <AppButton v-else @click="resetQuiz">重新作答</AppButton>
      </div>
    </div>

    <div v-if="questions.length" class="quiz-meta">
      <span class="quiz-pill">题目数 {{ questions.length }}</span>
      <span class="quiz-pill">来源：整份课件</span>
      <span class="quiz-pill">自动评分 + 错题回看</span>
    </div>

    <div v-if="!questions.length" class="quiz-empty">
      <strong>测验题尚未生成</strong>
      <p>当课件讲稿和知识点解析完成后，这里会自动生成可作答的课堂小测。</p>
    </div>

    <template v-else>
      <div v-if="submitted" class="quiz-score">
        <strong>{{ score }} / {{ questions.length }}</strong>
        <span>{{ scoreSummary }}</span>
      </div>

      <div v-if="submitted && reviewCards.length" class="quiz-review">
        <div class="quiz-review__title">
          <strong>错题回看建议</strong>
          <span>提交后自动给出重点回顾页，方便课堂收尾或课后复习。</span>
        </div>

        <div class="quiz-review__list">
          <article v-for="item in reviewCards" :key="item.key" class="quiz-review__item">
            <span class="quiz-review__page">建议回看第 {{ item.pageIndex }} 页</span>
            <strong>{{ item.label }}</strong>
            <p>{{ item.explanation }}</p>
          </article>
        </div>
      </div>

      <div class="quiz-list">
        <article v-for="(question, index) in questions" :key="question.id" class="quiz-item">
          <div class="quiz-item__head">
            <span class="quiz-index">Q{{ index + 1 }}</span>
            <span class="quiz-source">参考第 {{ question.sourcePageIndex }} 页</span>
          </div>

          <h3>{{ question.prompt }}</h3>

          <div class="quiz-options">
            <label
              v-for="option in question.options"
              :key="option.id"
              class="quiz-option"
              :class="optionState(question, option)"
            >
              <input
                v-model="answers[question.id]"
                type="radio"
                :name="question.id"
                :value="option.id"
                :disabled="submitted"
              />
              <span>{{ option.text }}</span>
            </label>
          </div>

          <div v-if="submitted" class="quiz-feedback">
            <strong>{{ isCorrect(question) ? '回答正确' : '回答有误' }}</strong>
            <p>{{ question.explanation }}</p>
          </div>
        </article>
      </div>
    </template>
  </AppCard>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { buildLectureQuiz } from '@/utils/lectureQuiz'

const props = defineProps({
  slides: {
    type: Array,
    default: () => [],
  },
})

const submitted = ref(false)
const answers = reactive({})

const questions = computed(() => buildLectureQuiz(props.slides))

const canSubmit = computed(
  () => questions.value.length > 0 && questions.value.every(question => Boolean(answers[question.id])),
)

const score = computed(() =>
  questions.value.reduce((total, question) => total + (isCorrect(question) ? 1 : 0), 0),
)

const scoreSummary = computed(() => {
  const ratio = questions.value.length ? score.value / questions.value.length : 0
  if (ratio >= 0.85) {
    return '掌握得很好，可以直接作为课堂讲解后的即时检验结果。'
  }
  if (ratio >= 0.6) {
    return '整体理解不错，建议结合错题回看对应页面再巩固一遍。'
  }
  return '建议先回顾讲稿与问答内容，再重新完成一轮随堂测验。'
})

const reviewCards = computed(() => {
  if (!submitted.value) {
    return []
  }

  const cards = questions.value
    .filter(question => !isCorrect(question))
    .map(question => ({
      key: `${question.id}-${question.sourcePageIndex}`,
      pageIndex: question.sourcePageIndex,
      label: question.focusLabel || question.prompt,
      explanation: question.explanation,
    }))

  const deduplicated = []
  const seen = new Set()
  cards.forEach(card => {
    const key = `${card.pageIndex}-${card.label}`
    if (seen.has(key)) {
      return
    }
    seen.add(key)
    deduplicated.push(card)
  })
  return deduplicated
})

watch(
  questions,
  nextQuestions => {
    for (const key of Object.keys(answers)) {
      delete answers[key]
    }
    nextQuestions.forEach(question => {
      answers[question.id] = ''
    })
    submitted.value = false
  },
  { immediate: true },
)

function submitQuiz() {
  if (!canSubmit.value) {
    return
  }
  submitted.value = true
}

function resetQuiz() {
  questions.value.forEach(question => {
    answers[question.id] = ''
  })
  submitted.value = false
}

function isCorrect(question) {
  const selected = answers[question.id]
  const correctOption = question.options.find(option => option.isCorrect)
  return Boolean(selected && correctOption && selected === correctOption.id)
}

function optionState(question, option) {
  if (!submitted.value) {
    return ''
  }
  if (option.isCorrect) {
    return 'quiz-option--correct'
  }
  return answers[question.id] === option.id ? 'quiz-option--wrong' : ''
}
</script>

<style scoped>
.quiz-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.92)),
    radial-gradient(circle at top right, rgba(255, 140, 58, 0.1), transparent 28%);
}

.quiz-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.quiz-label {
  color: var(--accent-color);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.quiz-header h2 {
  margin: 0.4rem 0 0;
  font-size: 1.55rem;
}

.quiz-header p {
  margin: 0.8rem 0 0;
  max-width: 42rem;
  color: var(--text-secondary);
  line-height: 1.8;
}

.quiz-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.quiz-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.quiz-pill {
  display: inline-flex;
  align-items: center;
  min-height: 1.95rem;
  padding: 0.32rem 0.72rem;
  border-radius: 999px;
  background: rgba(14, 90, 224, 0.08);
  color: var(--primary-color);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.quiz-empty {
  padding: 1rem 1.05rem;
  border-radius: var(--radius-lg);
  background: rgba(14, 90, 224, 0.05);
  border: 1px solid rgba(14, 90, 224, 0.09);
}

.quiz-empty strong {
  color: var(--text-primary);
}

.quiz-empty p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.quiz-score {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.05rem;
  border-radius: var(--radius-lg);
  background: rgba(15, 155, 107, 0.08);
  border: 1px solid rgba(15, 155, 107, 0.14);
}

.quiz-score strong {
  font-size: 1.7rem;
  line-height: 1;
  color: var(--success-color);
}

.quiz-score span {
  color: var(--text-secondary);
  line-height: 1.7;
}

.quiz-review {
  padding: 1rem 1.05rem;
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(14, 90, 224, 0.06), rgba(14, 90, 224, 0.03)),
    rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(14, 90, 224, 0.1);
}

.quiz-review__title {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.quiz-review__title strong {
  color: var(--text-primary);
}

.quiz-review__title span {
  color: var(--text-secondary);
  line-height: 1.7;
}

.quiz-review__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.85rem;
  margin-top: 1rem;
}

.quiz-review__item {
  padding: 0.9rem 0.95rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(104, 130, 171, 0.12);
}

.quiz-review__page {
  display: inline-flex;
  margin-bottom: 0.55rem;
  color: var(--primary-color);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.quiz-review__item strong {
  display: block;
  color: var(--text-primary);
}

.quiz-review__item p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.quiz-list {
  display: grid;
  gap: 1rem;
}

.quiz-item {
  padding: 1.1rem;
  border-radius: calc(var(--radius-lg) - 0.15rem);
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(104, 130, 171, 0.12);
}

.quiz-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.quiz-index,
.quiz-source {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.quiz-item h3 {
  margin: 0.85rem 0 0;
  font-size: 1.08rem;
  line-height: 1.6;
}

.quiz-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
  margin-top: 1rem;
}

.quiz-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.9rem 0.95rem;
  border-radius: var(--radius-md);
  border: 1px solid rgba(104, 130, 171, 0.12);
  background: rgba(246, 249, 255, 0.86);
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-base),
    background var(--transition-base);
}

.quiz-option:hover {
  transform: translateY(-1px);
  border-color: rgba(14, 90, 224, 0.22);
}

.quiz-option input {
  margin: 0.15rem 0 0;
}

.quiz-option span {
  color: var(--text-secondary);
  line-height: 1.75;
}

.quiz-option--correct {
  border-color: rgba(15, 155, 107, 0.22);
  background: rgba(15, 155, 107, 0.08);
}

.quiz-option--wrong {
  border-color: rgba(221, 79, 101, 0.22);
  background: rgba(221, 79, 101, 0.08);
}

.quiz-feedback {
  margin-top: 0.9rem;
  padding: 0.9rem 0.95rem;
  border-radius: var(--radius-md);
  background: rgba(14, 90, 224, 0.05);
  border: 1px solid rgba(14, 90, 224, 0.08);
}

.quiz-feedback strong {
  color: var(--text-primary);
}

.quiz-feedback p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

@media (max-width: 1024px) {
  .quiz-options {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .quiz-header {
    flex-direction: column;
  }

  .quiz-actions {
    width: 100%;
  }

  .quiz-actions > * {
    flex: 1;
  }

  .quiz-score {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
