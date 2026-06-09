const STATUS_ACTIONS = {
  UPLOADED: [
    { key: 'detail', label: '查看详情', variant: 'secondary', event: 'view-detail' },
    { key: 'parse', label: '等待解析', variant: 'ghost', disabled: true, event: 'view-detail' },
  ],
  PARSING: [
    { key: 'detail', label: '查看进度', variant: 'secondary', event: 'view-detail' },
  ],
  PARSED: [
    { key: 'detail', label: '查看解析结果', variant: 'secondary', event: 'view-detail' },
    { key: 'script', label: '生成讲稿', variant: 'primary', event: 'view-script' },
  ],
  GENERATING_SCRIPT: [
    { key: 'script-progress', label: '查看生成进度', variant: 'secondary', event: 'view-script' },
  ],
  READY: [
    { key: 'script', label: '查看讲稿', variant: 'secondary', event: 'view-script' },
    { key: 'lecture', label: '进入课堂', variant: 'primary', event: 'enter-lecture' },
  ],
  FAILED: [
    { key: 'detail', label: '查看错误', variant: 'secondary', event: 'view-detail' },
    { key: 'retry', label: '重新处理', variant: 'ghost', event: 'retry' },
  ],
}

export function getCoursewareActions(status) {
  const normalized = String(status || '').trim().toUpperCase()
  return STATUS_ACTIONS[normalized] || [
    { key: 'detail', label: '查看详情', variant: 'secondary', event: 'view-detail' },
  ]
}

