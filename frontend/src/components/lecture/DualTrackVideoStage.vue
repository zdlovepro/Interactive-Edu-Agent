<template>
  <section class="video-stage" :class="`mode-${activeMode}`" aria-label="课堂视频画面">
    <div class="video-stage__viewport">
      <video
        ref="lectureVideoRef"
        class="video-stage__track"
        :class="{ active: activeMode === VIDEO_TRACK_MODE.LECTURE }"
        :src="lectureVideoUrl"
        muted
        playsinline
        loop
        preload="auto"
        @error="handleTrackError(VIDEO_TRACK_MODE.LECTURE)"
      ></video>
      <video
        ref="standbyVideoRef"
        class="video-stage__track"
        :class="{ active: activeMode === VIDEO_TRACK_MODE.STANDBY }"
        :src="standbyVideoUrl"
        muted
        playsinline
        loop
        preload="auto"
        @error="handleTrackError(VIDEO_TRACK_MODE.STANDBY)"
      ></video>

      <div class="video-stage__overlay">
        <div>
          <span>{{ VIDEO_TRACK_LABEL[activeMode] }}</span>
          <strong>{{ title || `第 ${currentPage} 页` }}</strong>
        </div>
        <span class="video-stage__state">{{ statusLabel }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { LECTURE_STATE, LECTURE_STATUS_MAP, normalizeLectureStatus } from '@/constants/lecture'
import {
  SAMPLE_LECTURE_VIDEO_URL,
  SAMPLE_STANDBY_VIDEO_URL,
  VIDEO_TRACK_LABEL,
  VIDEO_TRACK_MODE,
} from '@/constants/videoTracks'

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
  isSpeaking: {
    type: Boolean,
    default: false,
  },
  lectureVideoUrl: {
    type: String,
    default: SAMPLE_LECTURE_VIDEO_URL,
  },
  standbyVideoUrl: {
    type: String,
    default: SAMPLE_STANDBY_VIDEO_URL,
  },
})

const lectureVideoRef = ref(null)
const standbyVideoRef = ref(null)
const failedTracks = ref(new Set())

const normalizedStatus = computed(() => normalizeLectureStatus(props.lectureStatus))
const activeMode = computed(() => {
  if (
    normalizedStatus.value === LECTURE_STATE.INTERRUPTED ||
    normalizedStatus.value === LECTURE_STATE.ANSWERING ||
    normalizedStatus.value === LECTURE_STATE.RESUMING
  ) {
    return VIDEO_TRACK_MODE.STANDBY
  }

  return VIDEO_TRACK_MODE.LECTURE
})
const statusLabel = computed(
  () => LECTURE_STATUS_MAP[normalizedStatus.value]?.text || LECTURE_STATUS_MAP[LECTURE_STATE.IDLE].text,
)

const videoByMode = mode =>
  mode === VIDEO_TRACK_MODE.STANDBY ? standbyVideoRef.value : lectureVideoRef.value

const shouldPlayTrack = mode => {
  if (failedTracks.value.has(mode)) {
    return false
  }
  if (mode !== activeMode.value) {
    return false
  }
  if (mode === VIDEO_TRACK_MODE.STANDBY) {
    return true
  }
  return normalizedStatus.value === LECTURE_STATE.PLAYING && props.isSpeaking
}

const applyPlaybackState = async () => {
  await nextTick()

  for (const mode of Object.values(VIDEO_TRACK_MODE)) {
    const video = videoByMode(mode)
    if (!video) {
      continue
    }

    if (shouldPlayTrack(mode)) {
      const playPromise = video.play()
      if (playPromise && typeof playPromise.catch === 'function') {
        playPromise.catch(() => {
          video.pause()
        })
      }
    } else {
      video.pause()
    }
  }
}

const handleTrackError = mode => {
  const nextFailedTracks = new Set(failedTracks.value)
  nextFailedTracks.add(mode)
  failedTracks.value = nextFailedTracks
}

watch(
  () => [activeMode.value, normalizedStatus.value, props.isSpeaking, props.currentPage],
  () => {
    void applyPlaybackState()
  },
)

onMounted(() => {
  void applyPlaybackState()
})

onUnmounted(() => {
  lectureVideoRef.value?.pause()
  standbyVideoRef.value?.pause()
})
</script>

<style scoped>
.video-stage {
  overflow: hidden;
  border: 1px solid rgba(145, 153, 183, 0.18);
  border-radius: var(--radius-lg);
  background: #111827;
  box-shadow: var(--shadow-sm);
}

.video-stage__viewport {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
}

.video-stage__track {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transform: scale(1.01);
  transition: opacity 220ms ease;
}

.video-stage__track.active {
  opacity: 1;
}

.video-stage__overlay {
  position: absolute;
  inset: auto 0 0;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
  color: #ffffff;
  background: linear-gradient(180deg, transparent, rgba(10, 16, 30, 0.72));
}

.video-stage__overlay span {
  display: block;
  margin-bottom: 0.25rem;
  color: rgba(255, 255, 255, 0.78);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.video-stage__overlay strong {
  display: block;
  max-width: 34rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-lg);
}

.video-stage__state {
  flex: 0 0 auto;
  min-width: 4.5rem;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  text-align: center;
}

@media (max-width: 640px) {
  .video-stage__overlay {
    align-items: flex-start;
    flex-direction: column;
  }

  .video-stage__overlay strong {
    max-width: 100%;
    font-size: var(--font-size-md);
  }
}
</style>
