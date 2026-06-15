<template>
  <div class="profile-page">
    <section class="page-shell page-section">
      <div class="profile-hero">
        <div class="profile-copy">
          <span class="eyebrow">个人中心</span>
          <h1 class="page-title">我的工作台</h1>
          <p class="page-description">
            这里聚合超星授权、导入入口和当前问答能力说明。资源库和视频资产入口已经收掉，课件流程统一从导入中心进入。
          </p>
        </div>
        <AppButton size="lg" @click="router.push('/imports')">前往导入中心</AppButton>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="summary-grid">
        <AppCard tone="glass" class="summary-card">
          <span>超星授权</span>
          <strong>{{ authStatusText }}</strong>
          <p>{{ authHint }}</p>
          <AppButton variant="secondary" size="sm" @click="router.push('/imports/chaoxing')">
            管理授权
          </AppButton>
        </AppCard>

        <AppCard tone="glass" class="summary-card">
          <span>导入中心</span>
          <strong>课件流程</strong>
          <p>本地上传、超星导入、URL 导入，以及后续讲稿和课堂链路都从这里开始。</p>
          <AppButton variant="secondary" size="sm" @click="router.push('/imports')">
            打开导入中心
          </AppButton>
        </AppCard>

        <AppCard tone="glass" class="summary-card">
          <span>本地上传</span>
          <strong>手动导入课件</strong>
          <p>如果你现在只想先跑通手动导入到生成视频这条主链路，直接从这里进入最快。</p>
          <AppButton variant="secondary" size="sm" @click="router.push('/imports/upload')">
            上传本地课件
          </AppButton>
        </AppCard>

        <AppCard tone="glass" class="summary-card">
          <span>RAG 助教</span>
          <strong>已启用课件问答</strong>
          <p>当前助教会基于已解析课件做问答与证据返回，后续补充资料时可以继续扩展知识范围。</p>
          <AppButton variant="secondary" size="sm" @click="router.push('/imports')">
            查看导入与问答链路
          </AppButton>
        </AppCard>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { useChaoxingAuthStore } from '@/stores/chaoxingAuth'

const router = useRouter()
const chaoxingAuthStore = useChaoxingAuthStore()

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

onMounted(() => {
  chaoxingAuthStore.restoreFromLocalStorage()
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.summary-card {
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

.summary-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.summary-card .app-button {
  margin-top: auto;
}

@media (max-width: 1080px) {
  .summary-grid {
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
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
