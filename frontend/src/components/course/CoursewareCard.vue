<template>
  <AppCard class="course-card" hoverable tone="glass">
    <div class="course-card__top">
      <div>
        <p class="course-card__eyebrow">课件资源</p>
        <h3 class="course-card__title">{{ courseware.name || '未命名课件' }}</h3>
      </div>
      <StatusBadge :label="statusMeta.text" :tone="statusMeta.tone" />
    </div>

    <div class="course-card__meta">
      <div class="meta-item">
        <span class="meta-label">更新时间</span>
        <span class="meta-value">{{ createdAtLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">任务状态</span>
        <span class="meta-value">{{ taskStatusLabel }}</span>
      </div>
    </div>

    <div class="course-card__actions">
      <AppButton
        v-for="action in actions"
        :key="action.key"
        :variant="action.variant"
        size="sm"
        :disabled="action.disabled"
        @click="emitAction(action)"
      >
        {{ action.label }}
      </AppButton>
    </div>
  </AppCard>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { getCoursewareStatusMeta, getTaskStatusLabel } from '@/constants/courseware'
import { formatDate } from '@/utils'
import { getCoursewareActions } from '@/utils/coursewareActions'

const props = defineProps({
  courseware: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['view-detail', 'view-script', 'enter-lecture', 'retry'])

const statusMeta = computed(() => getCoursewareStatusMeta(props.courseware.status))

const createdAtLabel = computed(() => {
  const value = props.courseware.updatedAt || props.courseware.createdAt
  return value ? formatDate(value) : '刚刚创建'
})

const taskStatusLabel = computed(() => getTaskStatusLabel(props.courseware.currentTaskStatus))

const actions = computed(() => getCoursewareActions(props.courseware.status))

function emitAction(action) {
  if (action.disabled) {
    return
  }
  emit(action.event, props.courseware)
}
</script>

<style scoped>
.course-card {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  min-height: 15rem;
}

.course-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.course-card__eyebrow {
  margin: 0 0 0.45rem;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.course-card__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.2rem;
  line-height: 1.35;
  word-break: break-word;
}

.course-card__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.9rem;
  border: 1px solid rgba(148, 157, 188, 0.12);
  border-radius: var(--radius-md);
  background: rgba(248, 250, 255, 0.9);
}

.meta-label {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.meta-value {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.course-card__actions {
  display: flex;
  gap: 0.75rem;
  margin-top: auto;
}

.course-card__actions > * {
  flex: 1;
}

@media (max-width: 640px) {
  .course-card__meta {
    grid-template-columns: 1fr;
  }

  .course-card__actions {
    flex-direction: column;
  }
}
</style>

