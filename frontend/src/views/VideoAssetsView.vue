<template>
  <div class="video-assets-page">
    <section class="page-shell page-section video-hero">
      <div class="video-hero__copy">
        <span class="eyebrow">I1-F 视频资产、HLS 转码与播放端</span>
        <h1 class="page-title">视频资产中心与 HLS 播放验收页</h1>
        <p class="page-description">
          这里把 I1-F 的后端转码链路和前端播放器整合到同一页，方便直接演示 sample.mp4 导入、FFmpeg
          转码、m3u8 播放、切换销毁和错误提示。
        </p>

        <div class="hero-metrics">
          <div class="metric-pill">
            <strong>{{ assets.length }}</strong>
            <span>资产总数</span>
          </div>
          <div class="metric-pill">
            <strong>{{ readyAssets.length }}</strong>
            <span>HLS 就绪</span>
          </div>
          <div class="metric-pill">
            <strong>{{ failedAssets.length }}</strong>
            <span>失败待处理</span>
          </div>
        </div>
      </div>

      <AppCard class="video-hero__guide" tone="accent">
        <div class="guide-header">
          <span class="pill">验收覆盖</span>
          <StatusBadge label="I1-F Ready" tone="accent" />
        </div>

        <div class="guide-list">
          <div class="guide-item">
            <strong>后端视频资产结构</strong>
            <span>支持 MP4 上传、sample 导入、状态查询、m3u8 与 ts 路径保存。</span>
          </div>
          <div class="guide-item">
            <strong>FFmpeg 转码与报错</strong>
            <span>FFmpeg 缺失时会返回明确错误，存在时输出标准 HLS 目录。</span>
          </div>
          <div class="guide-item">
            <strong>播放器销毁与移动端兼容</strong>
            <span>切换视频时销毁旧 HLS 实例，Safari 走原生 HLS，其他浏览器走 HLS.js。</span>
          </div>
        </div>
      </AppCard>
    </section>

    <section class="page-shell page-section video-layout">
      <AppCard class="video-actions-card" tone="glass">
        <div class="section-header">
          <div>
            <span class="eyebrow">视频接入</span>
            <h2 class="section-title">上传 MP4 或导入 sample.mp4</h2>
            <p class="section-description">
              当前任务不依赖真实数字人厂商结果，可以先用本地 sample.mp4 跑通整条 HLS 链路。
            </p>
          </div>
        </div>

        <div class="action-grid">
          <div class="field-block">
            <label class="field-label" for="video-file-input">MP4 文件</label>
            <input
              id="video-file-input"
              ref="fileInputRef"
              class="file-input"
              type="file"
              accept="video/mp4"
              @change="handleFileChange"
            />
            <p class="field-help">
              {{ selectedFile ? `已选择：${selectedFile.name}` : '建议先导入 sample.mp4，再验证转码和播放链路。' }}
            </p>
          </div>

          <div class="field-block">
            <label class="field-label" for="video-name-input">显示名称</label>
            <input
              id="video-name-input"
              v-model.trim="uploadName"
              class="app-input"
              type="text"
              placeholder="例如：数字人讲解示例"
            />
            <p class="field-help">不填写时默认使用文件名去掉扩展名。</p>
          </div>
        </div>

        <div class="action-buttons">
          <AppButton :disabled="!selectedFile || isUploading" @click="submitUpload">
            {{ isUploading ? '上传中...' : '上传 MP4 资产' }}
          </AppButton>
          <AppButton variant="secondary" :disabled="isImportingSample" @click="handleImportSample">
            {{ isImportingSample ? '导入中...' : '导入 sample.mp4' }}
          </AppButton>
          <AppButton variant="secondary" :disabled="isLoading" @click="refreshAssets">
            刷新资产列表
          </AppButton>
          <AppButton variant="ghost" @click="useStaticSamplePreview">
            播放预置 sample/index.m3u8
          </AppButton>
        </div>

        <div v-if="pageError" class="inline-alert inline-alert--danger">
          <span>{{ pageError }}</span>
          <button type="button" @click="pageError = ''">关闭</button>
        </div>

        <div class="inline-alert inline-alert--neutral">
          <span>
            如果后端机器未安装 FFmpeg，点击“转码”时会得到明确错误提示；播放器仍可先用预置 HLS
            样例完成前端验收。
          </span>
        </div>
      </AppCard>

      <AppCard class="video-asset-list-card" tone="subtle">
        <div class="section-header section-header--compact">
          <div>
            <span class="eyebrow">资产列表</span>
            <h2 class="section-title">选择要转码或播放的资产</h2>
          </div>
          <StatusBadge :label="`${assets.length} items`" tone="neutral" />
        </div>

        <EmptyState
          v-if="!assets.length && !isLoading"
          title="还没有视频资产"
          description="可以先导入 sample.mp4，或上传一段本地 MP4 作为后端转码输入。"
          action-label="导入 sample.mp4"
          @action="handleImportSample"
        />

        <div v-else class="asset-list">
          <article
            v-for="asset in assets"
            :key="asset.id"
            class="asset-item"
            :class="{ active: asset.id === selectedAssetId }"
          >
            <div class="asset-item__header">
              <div>
                <strong>{{ asset.name }}</strong>
                <p>{{ asset.originalFilename }}</p>
              </div>
              <StatusBadge
                :label="resolveStatusMeta(asset.status).label"
                :tone="resolveStatusMeta(asset.status).tone"
                compact
              />
            </div>

            <div class="asset-item__meta">
              <span>{{ asset.sample ? 'Sample 资产' : '上传资产' }}</span>
              <span>{{ formatAssetDate(asset.updatedAt) }}</span>
            </div>

            <div class="asset-item__actions">
              <AppButton variant="secondary" size="sm" @click="selectAssetPreview(asset)">
                {{ asset.playlistUrl ? '播放 HLS' : '预览 MP4' }}
              </AppButton>
              <AppButton
                size="sm"
                :disabled="transcodingAssetId === asset.id"
                @click="handleTranscode(asset)"
              >
                {{ transcodingAssetId === asset.id ? '转码中...' : '触发转码' }}
              </AppButton>
            </div>

            <div v-if="asset.errorMessage" class="asset-item__error">
              {{ asset.errorMessage }}
            </div>
          </article>
        </div>
      </AppCard>
    </section>

    <section class="page-shell page-section preview-layout">
      <AppCard class="preview-card" tone="glass">
        <div class="section-header section-header--compact">
          <div>
            <span class="eyebrow">播放预览</span>
            <h2 class="section-title">{{ previewLabel }}</h2>
            <p class="section-description">{{ previewDescription }}</p>
          </div>
          <StatusBadge :label="previewModeLabel" :tone="previewModeTone" />
        </div>

        <HlsVideoPlayer
          :src="previewUrl"
          :title="playerCaption"
          @error="handlePlayerError"
          @ready="playerError = ''"
        />

        <div v-if="playerError" class="inline-alert inline-alert--danger">
          <span>{{ playerError }}</span>
          <button type="button" @click="playerError = ''">关闭</button>
        </div>

        <div class="preview-actions">
          <AppButton variant="secondary" @click="useStaticSamplePreview">
            切回预置 HLS 样例
          </AppButton>
          <AppButton
            v-if="selectedAsset?.playlistUrl"
            variant="secondary"
            @click="selectAssetPreview(selectedAsset)"
          >
            重新加载当前资产 HLS
          </AppButton>
        </div>
      </AppCard>

      <AppCard class="preview-notes-card" tone="accent">
        <div class="section-header section-header--compact">
          <div>
            <span class="eyebrow">联调说明</span>
            <h2 class="section-title">推荐演示顺序</h2>
          </div>
        </div>

        <ol class="check-list">
          <li>先点“播放预置 sample/index.m3u8”，确认前端播放器可正常播放 m3u8。</li>
          <li>再点“导入 sample.mp4”，把示例 MP4 放入后端视频资产列表。</li>
          <li>机器已安装 FFmpeg 时，继续点击“触发转码”，检查状态切换到 HLS 就绪。</li>
          <li>切换不同资产反复播放，观察不会残留旧实例，也不会重复占用内存。</li>
          <li>机器未安装 FFmpeg 时，页面会显示明确错误提示，满足失败场景验收。</li>
        </ol>
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { importSampleVideoAsset, listVideoAssets, transcodeVideoAsset, uploadVideoAsset } from '@/api/videoAsset'
import HlsVideoPlayer from '@/components/video/HlsVideoPlayer.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { formatDate, getErrorMessage } from '@/utils'

const STATIC_SAMPLE_PLAYLIST = '/sample/index.m3u8'

const STATUS_META = {
  UPLOADED: {
    label: '已上传',
    tone: 'neutral',
  },
  TRANSCODING: {
    label: '转码中',
    tone: 'warning',
  },
  READY: {
    label: 'HLS 就绪',
    tone: 'success',
  },
  FAILED: {
    label: '转码失败',
    tone: 'danger',
  },
}

const assets = ref([])
const isLoading = ref(false)
const isUploading = ref(false)
const isImportingSample = ref(false)
const transcodingAssetId = ref('')
const selectedFile = ref(null)
const uploadName = ref('')
const selectedAssetId = ref('')
const previewUrl = ref(STATIC_SAMPLE_PLAYLIST)
const previewLabel = ref('预置 HLS 样例')
const previewDescription = ref('使用 frontend/public/sample/index.m3u8，可先独立验收前端 m3u8 播放能力。')
const playerCaption = ref('播放器会在切换源或页面卸载时主动销毁 Hls 实例。')
const pageError = ref('')
const playerError = ref('')
const fileInputRef = ref(null)

const readyAssets = computed(() => assets.value.filter(asset => asset.status === 'READY'))
const failedAssets = computed(() => assets.value.filter(asset => asset.status === 'FAILED'))
const selectedAsset = computed(() => assets.value.find(asset => asset.id === selectedAssetId.value) || null)
const previewModeLabel = computed(() => (String(previewUrl.value || '').includes('.m3u8') ? 'HLS / m3u8' : 'MP4 预览'))
const previewModeTone = computed(() => (previewModeLabel.value === 'HLS / m3u8' ? 'accent' : 'info'))

const resolveStatusMeta = status => STATUS_META[status] || STATUS_META.UPLOADED

const formatAssetDate = date => {
  if (!date) {
    return '刚刚更新'
  }
  return formatDate(date, 'YYYY-MM-DD HH:mm')
}

const refreshAssets = async ({ preserveSelection = true } = {}) => {
  isLoading.value = true
  pageError.value = ''

  try {
    const response = await listVideoAssets()
    assets.value = Array.isArray(response.data?.items) ? response.data.items : []

    if (!preserveSelection || !assets.value.some(asset => asset.id === selectedAssetId.value)) {
      const firstReadyAsset = assets.value.find(asset => asset.playlistUrl)
      if (firstReadyAsset) {
        selectAssetPreview(firstReadyAsset)
      }
    }
  } catch (error) {
    pageError.value = getErrorMessage(error, '视频资产列表加载失败，请稍后重试。')
  } finally {
    isLoading.value = false
  }
}

const resetUploadFields = () => {
  selectedFile.value = null
  uploadName.value = ''
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const handleFileChange = event => {
  selectedFile.value = event.target.files?.[0] || null
}

const submitUpload = async () => {
  if (!selectedFile.value) {
    pageError.value = '请先选择一个 MP4 文件。'
    return
  }

  isUploading.value = true
  pageError.value = ''

  try {
    const response = await uploadVideoAsset({
      file: selectedFile.value,
      name: uploadName.value,
    })
    const uploadedAssetId = response.data?.id
    await refreshAssets({ preserveSelection: false })

    const uploadedAsset = assets.value.find(asset => asset.id === uploadedAssetId)
    if (uploadedAsset) {
      selectAssetPreview(uploadedAsset)
    }
    resetUploadFields()
  } catch (error) {
    pageError.value = getErrorMessage(error, '视频上传失败，请检查文件格式后重试。')
  } finally {
    isUploading.value = false
  }
}

const handleImportSample = async () => {
  isImportingSample.value = true
  pageError.value = ''

  try {
    const response = await importSampleVideoAsset()
    const assetId = response.data?.id
    await refreshAssets({ preserveSelection: false })

    const importedAsset = assets.value.find(asset => asset.id === assetId)
    if (importedAsset) {
      selectAssetPreview(importedAsset)
    }
  } catch (error) {
    pageError.value = getErrorMessage(error, '导入 sample.mp4 失败，请确认样例文件已准备好。')
  } finally {
    isImportingSample.value = false
  }
}

const handleTranscode = async asset => {
  transcodingAssetId.value = asset.id
  pageError.value = ''

  try {
    await transcodeVideoAsset(asset.id)
    await refreshAssets()
    const updatedAsset = assets.value.find(item => item.id === asset.id)
    if (updatedAsset) {
      selectAssetPreview(updatedAsset)
    }
  } catch (error) {
    pageError.value = getErrorMessage(error, 'FFmpeg 转码失败，请检查服务端日志。')
    await refreshAssets()
  } finally {
    transcodingAssetId.value = ''
  }
}

const useStaticSamplePreview = () => {
  selectedAssetId.value = ''
  playerError.value = ''
  previewUrl.value = STATIC_SAMPLE_PLAYLIST
  previewLabel.value = '预置 HLS 样例'
  previewDescription.value = '使用 frontend/public/sample/index.m3u8，可先独立验收前端 m3u8 播放能力。'
  playerCaption.value = '推荐在移动端和桌面端都先验证这一条静态 HLS 播放链路。'
}

const selectAssetPreview = asset => {
  selectedAssetId.value = asset.id
  playerError.value = ''

  if (asset.playlistUrl) {
    previewUrl.value = asset.playlistUrl
    previewLabel.value = `${asset.name} · HLS 输出`
    previewDescription.value = '当前预览地址来自后端转码生成的 m3u8 播放清单。'
    playerCaption.value = `共保存 ${asset.segmentUrls?.length || 0} 个 ts 切片，支持切换时销毁旧实例。`
    return
  }

  previewUrl.value = asset.sourceUrl
  previewLabel.value = `${asset.name} · 原始 MP4`
  previewDescription.value = '当前资产尚未生成 HLS，先预览原始 MP4；完成转码后会自动切到 m3u8。'
  playerCaption.value = '如果点击“触发转码”后仍失败，请检查服务端机器是否已安装 FFmpeg。'
}

const handlePlayerError = message => {
  playerError.value = message || '视频播放失败，请稍后重试。'
}

onMounted(async () => {
  await refreshAssets({ preserveSelection: false })
})
</script>

<style scoped>
.video-assets-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.video-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.95fr);
  gap: 1.25rem;
  align-items: stretch;
}

.video-hero__copy,
.video-hero__guide {
  min-height: 100%;
}

.video-hero__copy {
  padding: 2rem 2.1rem;
  border-radius: calc(var(--radius-xl) + 0.15rem);
  background:
    radial-gradient(circle at top left, rgba(86, 116, 255, 0.18), transparent 30%),
    linear-gradient(165deg, rgba(255, 255, 255, 0.96), rgba(245, 248, 255, 0.88));
  border: 1px solid rgba(128, 142, 191, 0.14);
  box-shadow: var(--shadow-md);
}

.video-hero__copy h1 {
  margin: 0.4rem 0 0;
  font-size: clamp(2rem, 3vw, 2.8rem);
  line-height: 1.05;
  letter-spacing: -0.035em;
}

.video-hero__copy p {
  max-width: 48rem;
  margin: 1rem 0 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.hero-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  margin-top: 1.5rem;
}

.metric-pill {
  min-width: 8.25rem;
  padding: 0.85rem 1rem;
  border-radius: 1.15rem;
  background: rgba(247, 249, 255, 0.92);
  border: 1px solid rgba(121, 133, 188, 0.12);
}

.metric-pill strong {
  display: block;
  font-size: 1.3rem;
  color: var(--text-primary);
}

.metric-pill span {
  display: block;
  margin-top: 0.3rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

.guide-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.guide-list {
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
  margin-top: 1.25rem;
}

.guide-item {
  padding: 1rem 1rem 1rem 1.1rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(127, 140, 188, 0.12);
}

.guide-item strong {
  display: block;
  color: var(--text-primary);
}

.guide-item span {
  display: block;
  margin-top: 0.45rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.video-layout,
.preview-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 0.92fr);
  gap: 1.25rem;
  align-items: start;
}

.video-actions-card,
.video-asset-list-card,
.preview-card,
.preview-notes-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.section-header--compact {
  align-items: center;
}

.section-title {
  margin: 0.35rem 0 0;
  font-size: 1.45rem;
}

.section-description {
  margin: 0.6rem 0 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.field-label {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: 700;
}

.field-help {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}

.file-input {
  width: 100%;
  min-height: 3rem;
  padding: 0.85rem 1rem;
  border: 1px dashed rgba(108, 121, 180, 0.42);
  border-radius: var(--radius-md);
  background: rgba(251, 252, 255, 0.94);
  color: var(--text-secondary);
}

.action-buttons,
.preview-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.inline-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.85rem;
  padding: 0.9rem 1rem;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

.inline-alert button {
  color: inherit;
  cursor: pointer;
  font-weight: 700;
}

.inline-alert--danger {
  color: #b53f58;
  background: rgba(240, 74, 110, 0.1);
  border: 1px solid rgba(240, 74, 110, 0.14);
}

.inline-alert--neutral {
  color: var(--text-secondary);
  background: rgba(104, 118, 144, 0.08);
  border: 1px solid rgba(104, 118, 144, 0.1);
}

.asset-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.asset-item {
  padding: 1rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(129, 140, 184, 0.12);
  transition:
    transform var(--transition-base),
    border-color var(--transition-base),
    box-shadow var(--transition-base);
}

.asset-item.active {
  transform: translateY(-1px);
  border-color: rgba(96, 109, 255, 0.28);
  box-shadow: 0 16px 34px rgba(93, 104, 255, 0.14);
}

.asset-item__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.asset-item__header strong {
  display: block;
  color: var(--text-primary);
}

.asset-item__header p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.asset-item__meta {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.7rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.asset-item__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 0.85rem;
}

.asset-item__error {
  margin-top: 0.8rem;
  padding: 0.8rem 0.9rem;
  border-radius: 0.9rem;
  color: #b53f58;
  background: rgba(240, 74, 110, 0.08);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}

.check-list {
  margin: 0;
  padding-left: 1.2rem;
  color: var(--text-secondary);
  line-height: 1.85;
}

.check-list li + li {
  margin-top: 0.65rem;
}

@media (max-width: 1180px) {
  .video-hero,
  .video-layout,
  .preview-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .video-hero__copy {
    padding: 1.5rem;
  }

  .action-grid {
    grid-template-columns: 1fr;
  }

  .section-header,
  .asset-item__header,
  .asset-item__meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
