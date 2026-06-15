<template>
  <div class="player-shell">
    <div class="player-stage" :class="{ empty: !src }">
      <video ref="videoRef" class="player-video" controls preload="metadata"></video>

      <div v-if="!src" class="player-overlay">
        <strong>等待选择视频源</strong>
        <span>支持播放 m3u8，也支持在转码前预览原始 MP4。</span>
      </div>

      <div v-else-if="statusHint" class="player-overlay player-overlay--compact">
        <strong>{{ statusHint }}</strong>
      </div>
    </div>

    <div v-if="title" class="player-footer">
      <span>{{ title }}</span>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: '',
  },
  title: {
    type: String,
    default: '',
  },
  poster: {
    type: String,
    default: '',
  },
  autoplay: {
    type: Boolean,
    default: false,
  },
  muted: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['error', 'ready', 'loading'])

const videoRef = ref(null)
const hlsRef = ref(null)
const statusHint = ref('')
const suppressVideoEvents = ref(false)
let cachedHlsConstructor = null

const isHlsSource = source => String(source || '').toLowerCase().includes('.m3u8')

const destroyHlsInstance = () => {
  if (hlsRef.value) {
    hlsRef.value.destroy()
    hlsRef.value = null
  }
}

const resetVideoElement = () => {
  const video = videoRef.value
  if (!video) {
    return
  }

  video.pause()
  video.removeAttribute('src')
  video.load()
}

const cleanupPlayer = () => {
  suppressVideoEvents.value = true
  destroyHlsInstance()
  resetVideoElement()
  suppressVideoEvents.value = false
}

const playIfNeeded = async () => {
  if (!props.autoplay || !videoRef.value) {
    return
  }

  try {
    await videoRef.value.play()
  } catch (error) {
    emit('error', '浏览器阻止了自动播放，请手动点击播放按钮继续。')
  }
}

const loadHlsConstructor = async () => {
  if (cachedHlsConstructor) {
    return cachedHlsConstructor
  }

  const module = await import('hls.js/dist/hls.light.mjs')
  cachedHlsConstructor = module.default
  return cachedHlsConstructor
}

const handleFatalHlsError = (HlsConstructor, data) => {
  destroyHlsInstance()
  statusHint.value = ''

  if (data?.type === HlsConstructor.ErrorTypes.NETWORK_ERROR) {
    emit('error', 'HLS 网络错误，请检查 m3u8 与 ts 切片是否可访问。')
    return
  }

  if (data?.type === HlsConstructor.ErrorTypes.MEDIA_ERROR) {
    emit('error', 'HLS 媒体流解析失败，请重新转码或切换视频。')
    return
  }

  emit('error', 'HLS 播放初始化失败，请检查浏览器兼容性或切片文件。')
}

const attachSource = async () => {
  const video = videoRef.value
  if (!video) {
    return
  }

  cleanupPlayer()
  video.muted = props.muted
  video.crossOrigin = 'anonymous'
  video.playsInline = true
  video.setAttribute('playsinline', 'true')
  video.setAttribute('webkit-playsinline', 'true')

  if (props.poster) {
    video.poster = props.poster
  } else {
    video.removeAttribute('poster')
  }

  if (!props.src) {
    statusHint.value = ''
    return
  }

  emit('loading')
  statusHint.value = isHlsSource(props.src) ? '正在准备 HLS 视频流' : '正在加载源视频'

  if (isHlsSource(props.src) && video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = props.src
    video.load()
    return
  }

  if (isHlsSource(props.src)) {
    const HlsConstructor = await loadHlsConstructor()
    if (!HlsConstructor?.isSupported()) {
      statusHint.value = ''
      emit('error', '当前浏览器既不支持原生 HLS，也无法加载 HLS.js。')
      return
    }

    const hls = new HlsConstructor({
      enableWorker: true,
      lowLatencyMode: false,
      backBufferLength: 90,
    })

    hlsRef.value = hls
    hls.on(HlsConstructor.Events.MEDIA_ATTACHED, () => {
      hls.loadSource(props.src)
    })
    hls.on(HlsConstructor.Events.MANIFEST_PARSED, async () => {
      statusHint.value = ''
      await playIfNeeded()
    })
    hls.on(HlsConstructor.Events.ERROR, (_event, data) => {
      if (!data?.fatal) {
        return
      }
      handleFatalHlsError(HlsConstructor, data)
    })
    hls.attachMedia(video)
    return
  }

  video.src = props.src
  video.load()
  await playIfNeeded()
}

const handleLoadedMetadata = () => {
  if (suppressVideoEvents.value) {
    return
  }

  statusHint.value = ''
  emit('ready')
}

const handleVideoError = () => {
  if (!props.src || suppressVideoEvents.value) {
    return
  }

  statusHint.value = ''
  emit(
    'error',
    isHlsSource(props.src)
      ? '视频流加载失败，请检查 m3u8 清单和 ts 切片。'
      : '源视频加载失败，请检查 MP4 文件是否存在。',
  )
}

onMounted(() => {
  const video = videoRef.value
  if (!video) {
    return
  }

  video.addEventListener('loadedmetadata', handleLoadedMetadata)
  video.addEventListener('error', handleVideoError)
  void attachSource()
})

watch(
  () => props.src,
  async () => {
    await attachSource()
  },
)

onBeforeUnmount(() => {
  const video = videoRef.value
  if (video) {
    video.removeEventListener('loadedmetadata', handleLoadedMetadata)
    video.removeEventListener('error', handleVideoError)
  }
  cleanupPlayer()
})
</script>

<style scoped>
.player-shell {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.player-stage {
  position: relative;
  overflow: hidden;
  border-radius: calc(var(--radius-lg) + 0.1rem);
  background:
    radial-gradient(circle at top left, rgba(82, 112, 255, 0.2), transparent 28%),
    linear-gradient(160deg, rgba(12, 21, 49, 0.96), rgba(22, 34, 64, 0.94));
  box-shadow: 0 26px 60px rgba(19, 28, 63, 0.22);
}

.player-stage.empty {
  min-height: 20rem;
}

.player-video {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: transparent;
}

.player-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  gap: 0.4rem;
  padding: 1.5rem;
  text-align: center;
  color: rgba(246, 248, 255, 0.94);
  background: linear-gradient(180deg, rgba(12, 19, 45, 0.16), rgba(12, 19, 45, 0.56));
}

.player-overlay strong {
  display: block;
  font-size: 1.1rem;
}

.player-overlay span {
  color: rgba(222, 229, 255, 0.82);
  line-height: 1.7;
}

.player-overlay--compact {
  inset: auto 1rem 1rem auto;
  width: auto;
  padding: 0.65rem 0.95rem;
  border: 1px solid rgba(173, 186, 255, 0.12);
  border-radius: 999px;
  background: rgba(19, 29, 65, 0.8);
  backdrop-filter: blur(14px);
}

.player-footer {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

@media (max-width: 768px) {
  .player-stage.empty {
    min-height: 15rem;
  }

  .player-overlay {
    padding: 1.1rem;
  }
}
</style>
