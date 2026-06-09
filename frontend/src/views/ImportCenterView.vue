<template>
  <div class="import-center-page">
    <section class="page-shell page-section import-center-hero">
      <div>
        <span class="eyebrow">导入中心</span>
        <h1 class="page-title">选择课件资源的进入方式</h1>
        <p class="page-description">
          这里负责“创建课件资源”。已经导入或上传完成的内容，请到资源库继续查看解析、讲稿和课堂入口。
        </p>
      </div>
    </section>

    <section class="page-shell page-section">
      <div class="import-method-grid">
        <AppCard
          v-for="item in importMethods"
          :key="item.to"
          class="import-method-card"
          tone="glass"
          hoverable
        >
          <span class="method-badge" :class="`tone-${item.tone}`">{{ item.badge }}</span>
          <h2>{{ item.title }}</h2>
          <p>{{ item.description }}</p>
          <AppButton :variant="item.primary ? 'primary' : 'secondary'" @click="router.push(item.to)">
            {{ item.action }}
          </AppButton>
        </AppCard>
      </div>
    </section>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'

const router = useRouter()

const importMethods = [
  {
    title: '本地上传',
    badge: '稳定可用',
    tone: 'success',
    description: '上传 PDF、PPT、PPTX 等课件文件，进入现有解析和讲稿生成流程。',
    action: '上传本地课件',
    to: '/imports/upload',
    primary: true,
  },
  {
    title: '超星扫码导入',
    badge: '需要授权',
    tone: 'accent',
    description: '通过学习通扫码授权，自动发现课程页中的课件图片、PDF、PPT 和附件。',
    action: '从超星导入',
    to: '/imports/chaoxing',
  },
  {
    title: '普通 URL 导入',
    badge: '实验功能',
    tone: 'warning',
    description: '适合直接指向 PDF/PPTX/图片资源的链接；网页爬取仍需要 crawler worker 支持。',
    action: '导入 URL',
    to: '/imports/url',
  },
]
</script>

<style scoped>
.import-center-hero {
  padding-bottom: 0;
}

.import-method-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.2rem;
}

.import-method-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 19rem;
}

.import-method-card h2 {
  margin: 0;
  font-size: 1.45rem;
}

.import-method-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.import-method-card .app-button {
  margin-top: auto;
}

.method-badge {
  width: fit-content;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.tone-success {
  color: var(--success-color);
  background: rgba(31, 157, 103, 0.12);
}

.tone-accent {
  color: var(--primary-color);
  background: rgba(95, 104, 255, 0.12);
}

.tone-warning {
  color: var(--warning-color);
  background: rgba(228, 156, 49, 0.14);
}

@media (max-width: 960px) {
  .import-method-grid {
    grid-template-columns: 1fr;
  }
}
</style>

