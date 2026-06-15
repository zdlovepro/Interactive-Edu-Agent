<template>
  <section class="video-stage" aria-label="课堂视频画面">
    <div class="video-stage__header">
      <div class="video-stage__title-group">
        <span class="video-stage__eyebrow">课堂视频</span>
        <strong>{{ title || `第 ${currentPage} 页` }}</strong>
      </div>

      <div class="video-stage__status-group">
        <span class="video-stage__pill">{{ lectureStatusText }}</span>
        <span class="video-stage__pill" :class="`is-${normalizedVideoStatus}`">
          {{ videoStatusLabel }}
        </span>
      </div>
    </div>

    <div class="video-stage__body">
      <HlsVideoPlayer
        v-if="videoSrc"
        :src="videoSrc"
        :title="playerTitle"
        :muted="muted"
        @error="playerError = $event"
        @ready="playerError = ''"
      />

      <div v-else class="video-stage__placeholder">
        <strong>当前还没有可播放的生成视频</strong>
        <p>{{ placeholderText }}</p>
      </div>
    </div>

    <p class="video-stage__hint">{{ videoStatusText || defaultHint }}</p>
    <div v-if="playerError" class="video-stage__error">{{ playerError }}</div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import HlsVideoPlayer from '@/components/video/HlsVideoPlayer.vue'
import { LECTURE_STATE, LECTURE_STATUS_MAP, normalizeLectureStatus } from '@/constants/lecture'

const props = defineProps({
  lectureStatus: {
    type: String,
    default: LECTURE_STATE.IDLE,
  },
  currentPage: {
    type: Number,
    default: 1,
  },
  title: {
    type: String,
    default: '',
  },
  videoSrc: {
    type: String,
    default: '',
  },
  videoStatus: {
    type: String,
    default: '',
  },
  videoStatusText: {
    type: String,
    default: '',
  },
  muted: {
    type: Boolean,
    default: true,
  },
})

const playerError = ref('')

const normalizedLectureStatus = computed(() => normalizeLectureStatus(props.lectureStatus))
const normalizedVideoStatus = computed(() =>
  String(props.videoStatus || '').trim().toUpperCase() || 'UNAVAILABLE',
)

const lectureStatusText = computed(
  () =>
    LECTURE_STATUS_MAP[normalizedLectureStatus.value]?.text ||
    LECTURE_STATUS_MAP[LECTURE_STATE.IDLE].text,
)

const videoStatusLabel = computed(() => {
  switch (normalizedVideoStatus.value) {
    case 'READY':
      return '视频已就绪'
    case 'RENDERING':
      return '视频生成中'
    case 'FAILED':
      return '视频生成失败'
    case 'PENDING':
      return '等待生成'
    default:
      return '暂未生成'
  }
})

const playerTitle = computed(() => props.title || `课堂讲解视频 · 第 ${props.currentPage} 页`)

const placeholderText = computed(() => {
  switch (normalizedVideoStatus.value) {
    case 'RENDERING':
      return '讲解视频正在生成中，稍后会自动出现在这里。'
    case 'FAILED':
      return '生成任务失败了，请回到讲稿页重新触发视频生成。'
    default:
      return '请先在讲稿页完成视频生成，课堂页就会直接展示真实生成结果。'
  }
})

const defaultHint = computed(() => {
  if (props.videoSrc) {
    return '这里展示的是当前课件的真实生成视频，不再使用示例素材。'
  }
  return '当前课堂仍可继续看讲稿和问答，但视频需要先完成渲染。'
})
</script>

<style scoped>
.video-stage {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1rem;
  border: 1px solid rgba(145, 153, 183, 0.18);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at top left, rgba(82, 112, 255, 0.12), transparent 28%),
    rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-sm);
}

.video-stage__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.video-stage__title-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.video-stage__eyebrow {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.video-stage__title-group strong {
  font-size: 1.15rem;
  color: var(--text-primary);
}

.video-stage__status-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.55rem;
}

.video-stage__pill {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  background: rgba(122, 132, 181, 0.12);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.video-stage__pill.is-ready {
  background: rgba(31, 157, 103, 0.12);
  color: var(--success-color);
}

.video-stage__pill.is-rendering,
.video-stage__pill.is-pending {
  background: rgba(95, 104, 255, 0.12);
  color: var(--primary-color);
}

.video-stage__pill.is-failed {
  background: rgba(203, 65, 94, 0.12);
  color: var(--error-color);
}

.video-stage__body {
  min-height: 16rem;
}

.video-stage__placeholder {
  display: grid;
  place-items: center;
  min-height: 20rem;
  padding: 1.5rem;
  border-radius: calc(var(--radius-lg) + 0.1rem);
  background:
    radial-gradient(circle at top left, rgba(82, 112, 255, 0.18), transparent 30%),
    linear-gradient(160deg, rgba(12, 21, 49, 0.96), rgba(22, 34, 64, 0.94));
  text-align: center;
  color: rgba(246, 248, 255, 0.94);
}

.video-stage__placeholder strong {
  font-size: 1.15rem;
}

.video-stage__placeholder p,
.video-stage__hint {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.video-stage__placeholder p {
  max-width: 34rem;
  color: rgba(222, 229, 255, 0.82);
}

.video-stage__error {
  padding: 0.9rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(203, 65, 94, 0.08);
  border: 1px solid rgba(203, 65, 94, 0.14);
  color: var(--error-color);
  line-height: 1.7;
}

@media (max-width: 768px) {
  .video-stage__header {
    flex-direction: column;
  }

  .video-stage__status-group {
    justify-content: flex-start;
  }
}
</style>
