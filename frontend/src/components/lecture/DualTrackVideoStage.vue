<template>
  <section class="video-stage" aria-label="课堂视频画面">
    <HlsVideoPlayer
      v-if="videoSrc"
      ref="playerRef"
      class="video-stage__player"
      :src="videoSrc"
      :muted="muted"
      @error="playerError = $event"
      @ready="playerError = ''"
      @timeupdate="$emit('timeupdate', $event)"
      @play="$emit('play', $event)"
      @pause="$emit('pause', $event)"
    />

    <div v-else class="video-stage__placeholder">
      <strong>当前还没有可播放的生成视频</strong>
      <p>{{ placeholderText }}</p>
    </div>

    <div v-if="playerError" class="video-stage__error">{{ playerError }}</div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import HlsVideoPlayer from '@/components/video/HlsVideoPlayer.vue'

const props = defineProps({
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

defineEmits(['timeupdate', 'play', 'pause'])

const playerError = ref('')
const playerRef = ref(null)
const normalizedVideoStatus = computed(() =>
  String(props.videoStatus || '').trim().toUpperCase() || 'UNAVAILABLE',
)

const pause = () => playerRef.value?.pause?.() ?? false
const play = async () => playerRef.value?.play?.() ?? false
const seek = seconds => playerRef.value?.seek?.(seconds) ?? false
const getCurrentTime = () => playerRef.value?.getCurrentTime?.() ?? 0
const getDuration = () => playerRef.value?.getDuration?.() ?? 0
const isPaused = () => playerRef.value?.isPaused?.() ?? true

const placeholderText = computed(() => {
  if (props.videoStatusText) {
    return props.videoStatusText
  }

  switch (normalizedVideoStatus.value) {
    case 'RENDERING':
      return '讲解视频正在生成中，稍后会自动出现在这里。'
    case 'FAILED':
      return '生成任务失败了，请回到讲稿页重新触发视频生成。'
    default:
      return '请先在讲稿页完成视频生成，课堂页就会直接展示真实生成结果。'
  }
})

defineExpose({
  pause,
  play,
  seek,
  getCurrentTime,
  getDuration,
  isPaused,
})
</script>

<style scoped>
.video-stage {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 0.9rem;
  border: 1px solid rgba(145, 153, 183, 0.18);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at top left, rgba(82, 112, 255, 0.12), transparent 28%),
    rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-sm);
}

.video-stage__player :deep(.player-stage) {
  min-height: clamp(23rem, 56vh, 42rem);
}

.video-stage__player :deep(.player-video) {
  min-height: clamp(23rem, 56vh, 42rem);
  object-fit: contain;
}

.video-stage__placeholder {
  display: grid;
  place-items: center;
  min-height: clamp(23rem, 56vh, 42rem);
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

.video-stage__placeholder p {
  margin: 0;
  max-width: 34rem;
  color: rgba(222, 229, 255, 0.82);
  line-height: 1.7;
}

.video-stage__error {
  padding: 0.9rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(203, 65, 94, 0.08);
  border: 1px solid rgba(203, 65, 94, 0.14);
  color: var(--error-color);
  line-height: 1.7;
}
</style>
