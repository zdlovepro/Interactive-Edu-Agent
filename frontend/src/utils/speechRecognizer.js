function resolveSpeechRecognitionConstructor() {
  if (typeof globalThis === 'undefined') {
    return null
  }

  return globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition || null
}

function normalizeSpeechRecognitionError(event) {
  const code = String(event?.error || event?.name || 'unknown').trim().toLowerCase()

  let message = '语音识别失败，请稍后重试。'
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      message = '无法访问麦克风，请检查浏览器权限。'
      break
    case 'audio-capture':
      message = '没有检测到可用麦克风，请检查设备。'
      break
    case 'network':
      message = '语音识别服务连接失败，请检查网络。'
      break
    case 'no-speech':
      message = '没有检测到清晰语音，请再试一次。'
      break
    case 'aborted':
      message = '语音识别已结束。'
      break
    default:
      break
  }

  const error = new Error(message)
  error.code = code
  return error
}

function extractTranscript(results) {
  let transcript = ''
  let finalTranscript = ''
  let interimTranscript = ''

  for (const result of Array.from(results || [])) {
    const text = String(result?.[0]?.transcript || '').trim()
    if (!text) {
      continue
    }

    transcript += `${text} `
    if (result.isFinal) {
      finalTranscript += `${text} `
    } else {
      interimTranscript += `${text} `
    }
  }

  return {
    transcript: transcript.trim(),
    finalTranscript: finalTranscript.trim(),
    interimTranscript: interimTranscript.trim(),
    hasFinal: Boolean(finalTranscript.trim()),
  }
}

class SpeechRecognizer {
  constructor(options = {}) {
    this.options = {
      lang: 'zh-CN',
      continuous: true,
      interimResults: true,
      maxAlternatives: 1,
      onStart: null,
      onEnd: null,
      onResult: null,
      onError: null,
      ...options,
    }

    this.recognition = null
    this.isListening = false
    this.manualStopRequested = false
  }

  ensureSupported() {
    if (!resolveSpeechRecognitionConstructor()) {
      throw new Error('当前浏览器不支持语音识别。')
    }
  }

  setCallbacks(callbacks = {}) {
    this.options = {
      ...this.options,
      ...callbacks,
    }
  }

  ensureRecognition() {
    this.ensureSupported()

    if (this.recognition) {
      return this.recognition
    }

    const RecognitionConstructor = resolveSpeechRecognitionConstructor()
    const recognition = new RecognitionConstructor()

    recognition.lang = this.options.lang
    recognition.continuous = this.options.continuous
    recognition.interimResults = this.options.interimResults
    recognition.maxAlternatives = this.options.maxAlternatives

    recognition.onstart = () => {
      this.isListening = true
      this.options.onStart?.()
    }

    recognition.onend = () => {
      this.isListening = false
      this.options.onEnd?.({
        manualStop: this.manualStopRequested,
      })
    }

    recognition.onresult = event => {
      this.options.onResult?.(extractTranscript(event.results))
    }

    recognition.onerror = event => {
      this.options.onError?.(normalizeSpeechRecognitionError(event))
    }

    this.recognition = recognition
    return recognition
  }

  start() {
    const recognition = this.ensureRecognition()
    if (this.isListening) {
      return false
    }

    this.manualStopRequested = false
    recognition.lang = this.options.lang
    recognition.continuous = this.options.continuous
    recognition.interimResults = this.options.interimResults
    recognition.maxAlternatives = this.options.maxAlternatives
    recognition.start()
    return true
  }

  stop() {
    if (!this.recognition) {
      return false
    }

    this.manualStopRequested = true
    if (this.isListening) {
      this.recognition.stop()
    }
    return true
  }

  abort() {
    if (!this.recognition) {
      return false
    }

    this.manualStopRequested = true
    if (typeof this.recognition.abort === 'function') {
      this.recognition.abort()
    } else if (this.isListening) {
      this.recognition.stop()
    }
    return true
  }

  destroy() {
    if (this.recognition) {
      this.manualStopRequested = true
      this.recognition.onstart = null
      this.recognition.onend = null
      this.recognition.onresult = null
      this.recognition.onerror = null

      try {
        if (typeof this.recognition.abort === 'function') {
          this.recognition.abort()
        } else if (this.isListening) {
          this.recognition.stop()
        }
      } catch {
        // Ignore destroy-time teardown errors.
      }
    }

    this.recognition = null
    this.isListening = false
  }
}

export function createSpeechRecognizer(options) {
  return new SpeechRecognizer(options)
}

export default createSpeechRecognizer
