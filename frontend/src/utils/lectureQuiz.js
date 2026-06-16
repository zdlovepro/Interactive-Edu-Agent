const GENERIC_DISTRACTORS = [
  '支持向量机与分类间隔',
  '决策树剪枝与集成学习',
  '卷积神经网络与图像分割',
  'Transformer 注意力机制',
  '强化学习与策略梯度',
]

const NOISE_PATTERNS = [
  /^topics?$/i,
  /^practice$/i,
  /^closing$/i,
  /^summary$/i,
  /^outline$/i,
  /^contents?$/i,
  /^page\s*\d+$/i,
  /^p(age)?\s*\d+$/i,
  /^no\.?\s+of\s+views$/i,
  /^dr\./i,
]

const CONCEPT_PATTERNS = [
  { pattern: /线性回归|linear regression/i, label: '线性回归' },
  { pattern: /回归|regression/i, label: '回归问题' },
  { pattern: /梯度下降|gradient descent/i, label: '梯度下降' },
  { pattern: /优化方法|optimization methods?/i, label: '优化方法' },
  { pattern: /损失函数|loss function/i, label: '损失函数' },
  { pattern: /代价函数|cost function/i, label: '代价函数' },
  { pattern: /机器学习|machine learning/i, label: '机器学习' },
  { pattern: /参数|parameter/i, label: '模型参数学习' },
]

const CONCEPT_RULES = [
  {
    key: 'gradient',
    match: slide => /梯度下降|gradient/i.test(joinSlideText(slide)),
    build: slide => ({
      kind: 'concept',
      prompt: '关于梯度下降，本课强调它是如何更新参数的？',
      correctText: '沿着负梯度方向逐步更新参数，让损失尽量下降',
      distractors: [
        '沿着梯度方向更新参数，让损失尽量增大',
        '直接枚举所有参数组合，不需要梯度信息',
        '固定参数不变，只比较不同模型结构',
      ],
      explanation: `第 ${slide.pageIndex} 页说明了梯度下降的核心思想：依据梯度方向迭代更新参数，以持续减小目标函数值。`,
      sourcePageIndex: slide.pageIndex,
      focusLabel: '梯度下降',
    }),
  },
  {
    key: 'loss',
    match: slide => /损失|loss/i.test(joinSlideText(slide)),
    build: slide => ({
      kind: 'concept',
      prompt: '损失函数在本课里最核心的作用是什么？',
      correctText: '衡量一组参数或预测结果到底好不好',
      distractors: [
        '只用来决定页面排版和可视化效果',
        '替代所有优化算法，直接给出最优参数',
        '直接生成训练数据，不参与模型评估',
      ],
      explanation: `第 ${slide.pageIndex} 页把损失函数作为评价预测误差与参数优劣的关键依据，是后续优化过程的目标。`,
      sourcePageIndex: slide.pageIndex,
      focusLabel: '损失函数',
    }),
  },
  {
    key: 'linear-model',
    match: slide => /未知参数|linear regression|线性回归|weight|bias/i.test(joinSlideText(slide)),
    build: slide => ({
      kind: 'concept',
      prompt: '在线性回归的建模阶段，本课把哪些内容视为需要从数据中学习的未知参数？',
      correctText: '模型中的权重和偏置等参数',
      distractors: [
        '训练样本的页码和课程标题',
        '损失函数的名字与图表颜色',
        '所有输入特征本身的原始取值',
      ],
      explanation: `第 ${slide.pageIndex} 页强调，模型形式可以先给定，但参数值需要通过数据训练得到。`,
      sourcePageIndex: slide.pageIndex,
      focusLabel: '模型参数学习',
    }),
  },
]

export function buildLectureQuiz(slides = [], version = 0) {
  const normalizedSlides = normalizeSlides(slides)
  if (!normalizedSlides.length) {
    return []
  }

  const questions = [buildOverviewQuestion(normalizedSlides, version)]
  const usedPages = new Set([questions[0].sourcePageIndex])

  for (const rule of CONCEPT_RULES) {
    const matchedSlide = normalizedSlides.find(slide => rule.match(slide) && !usedPages.has(slide.pageIndex))
    if (!matchedSlide) {
      continue
    }

    questions.push(
      finalizeQuestion(
        {
          id: `rule-${rule.key}`,
          ...rule.build(matchedSlide),
        },
        version + questions.length,
      ),
    )
    usedPages.add(matchedSlide.pageIndex)
  }

  const genericCandidates = rotateArray(normalizedSlides, version).filter(
    slide => slideOptionLabel(slide) && !usedPages.has(slide.pageIndex),
  )

  for (let index = 0; index < genericCandidates.length && questions.length < 4; index += 1) {
    const slide = genericCandidates[index]
    const optionPool = buildSlideOptions(normalizedSlides, slide, version + index)
    const correctText = slideOptionLabel(slide)
    if (!correctText || optionPool.length < 4) {
      continue
    }

    questions.push(
      finalizeQuestion(
        {
          id: `page-topic-${slide.pageIndex}`,
          kind: 'generic',
          prompt: `第 ${slide.pageIndex} 页最适合作为下面哪个主题的展开？`,
          correctText,
          distractors: optionPool.filter(item => item !== correctText).slice(0, 3),
          explanation: `第 ${slide.pageIndex} 页围绕“${correctText}”展开，是课堂内容中的一个明确讲解节点。`,
          sourcePageIndex: slide.pageIndex,
          focusLabel: correctText,
        },
        version + questions.length,
      ),
    )
  }

  return questions.slice(0, 4)
}

function normalizeSlides(slides) {
  return slides
    .map((slide, index) => ({
      id: slide?.id || `slide-${index + 1}`,
      pageIndex: Number(slide?.pageIndex) || index + 1,
      title: sanitizeLabel(slide?.title),
      content: sanitizeContent(slide?.content),
      knowledgePoints: Array.isArray(slide?.knowledgePoints)
        ? slide.knowledgePoints.map(item => sanitizeLabel(item)).filter(Boolean)
        : [],
      concepts: extractConceptsFromText(
        [slide?.title, slide?.content, ...(slide?.knowledgePoints || [])].filter(Boolean).join(' '),
      ),
    }))
    .filter(slide => slide.title || slide.content || slide.knowledgePoints.length || slide.concepts.length)
}

function buildOverviewQuestion(slides, version) {
  const concepts = unique(slides.flatMap(slide => slide.concepts)).slice(0, 3)
  const fallbackLabels = unique(slides.map(slide => slideOptionLabel(slide))).slice(0, 3)
  const correctText = (concepts.length ? concepts : fallbackLabels).join('、')
  const distractors = rotateArray(GENERIC_DISTRACTORS, version).slice(0, 3)

  return finalizeQuestion(
    {
      id: 'overview',
      kind: 'overview',
      prompt: '从整份课件来看，本节课的主线最接近下面哪一项？',
      correctText,
      distractors,
      explanation: `整份课件的内容主线集中在“${correctText}”，后续页面都在围绕这些主题展开讲解与推导。`,
      sourcePageIndex: slides[0]?.pageIndex || 1,
      focusLabel: '课程主线',
    },
    version,
  )
}

function finalizeQuestion(question, offset) {
  const optionTexts = unique([
    question.correctText,
    ...(question.distractors || []),
    ...rotateArray(GENERIC_DISTRACTORS, offset),
  ]).slice(0, 4)

  const options = optionTexts.map((text, index) => ({
    id: `option-${offset}-${index + 1}`,
    text,
    isCorrect: text === question.correctText,
  }))

  return {
    id: question.id,
    kind: question.kind,
    prompt: question.prompt,
    explanation: question.explanation,
    sourcePageIndex: question.sourcePageIndex,
    focusLabel: question.focusLabel || question.correctText,
    options: rotateArray(options, offset % Math.max(options.length, 1)),
  }
}

function buildSlideOptions(slides, targetSlide, version) {
  const labels = rotateArray(
    slides
      .filter(slide => slide.id !== targetSlide.id)
      .map(slide => slideOptionLabel(slide))
      .filter(Boolean),
    version,
  )

  return unique([slideOptionLabel(targetSlide), ...labels, ...GENERIC_DISTRACTORS]).slice(0, 4)
}

function slideOptionLabel(slide) {
  const knowledgePoint = preferredKnowledgePoint(slide)
  if (knowledgePoint) {
    return knowledgePoint
  }

  if (slide?.concepts?.length) {
    return slide.concepts[0]
  }

  if (slide?.title) {
    return slide.title
  }

  return `第 ${slide?.pageIndex || '?'} 页核心内容`
}

function preferredKnowledgePoint(slide) {
  const candidates = Array.isArray(slide?.knowledgePoints) ? slide.knowledgePoints : []
  const title = String(slide?.title || '').trim()

  return (
    candidates.find(
      item =>
        item &&
        item !== title &&
        item.length <= 24 &&
        !NOISE_PATTERNS.some(pattern => pattern.test(item)),
    ) ||
    candidates[0] ||
    ''
  )
}

function sanitizeLabel(value) {
  const text = String(value || '')
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^[\d.()\-\s]+/, '')
    .trim()

  if (!text) {
    return ''
  }

  if (NOISE_PATTERNS.some(pattern => pattern.test(text))) {
    return ''
  }

  return text
}

function sanitizeContent(value) {
  return String(value || '')
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function extractConceptsFromText(text) {
  const joinedText = String(text || '')
  return unique(
    CONCEPT_PATTERNS.filter(({ pattern }) => pattern.test(joinedText)).map(({ label }) => label),
  )
}

function joinSlideText(slide) {
  return [slide?.title, slide?.content, ...(slide?.knowledgePoints || []), ...(slide?.concepts || [])].join(' ')
}

function rotateArray(list, offset) {
  if (!Array.isArray(list) || !list.length) {
    return []
  }

  const safeOffset = ((offset % list.length) + list.length) % list.length
  return [...list.slice(safeOffset), ...list.slice(0, safeOffset)]
}

function unique(list) {
  return Array.from(new Set((list || []).filter(Boolean)))
}
