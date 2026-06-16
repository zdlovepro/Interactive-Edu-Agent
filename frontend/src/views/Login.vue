<template>
  <div class="login-page">
    <section class="login-shell">
      <div class="login-hero">
        <span class="eyebrow">Role-based Access</span>
        <h1>{{ isRegisterMode ? '注册并进入 IEA 智能教学助手' : '登录 IEA 智能教学助手' }}</h1>
        <p>
          教师可以上传课件、生成讲稿与讲解视频，并设置课程号供学生访问。
          学生在此基础上还可以进入互动课堂、使用语音打断和 AI 助教问答。
        </p>

        <div class="login-highlights">
          <div class="highlight-item">
            <strong>教师模式</strong>
            <span>管理课程资源，设置课程号，并完成课前准备与课堂演示预览。</span>
          </div>
          <div class="highlight-item">
            <strong>学生模式</strong>
            <span>通过课程号加入教师共享课件，并使用完整的互动课堂能力。</span>
          </div>
        </div>
      </div>

      <AppCard class="login-card" tone="accent">
        <div class="login-card__header">
          <div>
            <span class="eyebrow">{{ isRegisterMode ? 'Register' : 'Sign In' }}</span>
            <h2>{{ isRegisterMode ? '创建新账号' : '选择身份并登录' }}</h2>
          </div>
          <span class="login-badge">Persistent</span>
        </div>

        <div class="mode-switch">
          <button
            type="button"
            class="mode-switch__item"
            :class="{ active: mode === 'login' }"
            @click="setMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            class="mode-switch__item"
            :class="{ active: mode === 'register' }"
            @click="setMode('register')"
          >
            注册
          </button>
        </div>

        <form class="login-form" @submit.prevent="handleSubmit">
          <template v-if="isRegisterMode">
            <div class="role-switch">
              <button
                type="button"
                class="role-switch__item"
                :class="{ active: registerForm.role === 'TEACHER' }"
                @click="registerForm.role = 'TEACHER'"
              >
                教师注册
              </button>
              <button
                type="button"
                class="role-switch__item"
                :class="{ active: registerForm.role === 'STUDENT' }"
                @click="registerForm.role = 'STUDENT'"
              >
                学生注册
              </button>
            </div>

            <label class="field-block">
              <span class="field-label">真实姓名</span>
              <input
                v-model.trim="registerForm.realName"
                class="app-input"
                type="text"
                autocomplete="name"
                placeholder="例如：张三"
              />
            </label>
          </template>

          <label class="field-block">
            <span class="field-label">用户名</span>
            <input
              v-model.trim="activeForm.username"
              class="app-input"
              type="text"
              autocomplete="username"
              placeholder="输入用户名"
            />
          </label>

          <label class="field-block">
            <span class="field-label">密码</span>
            <input
              v-model="activeForm.password"
              class="app-input"
              :type="passwordVisible ? 'text' : 'password'"
              :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
              placeholder="至少 6 位"
            />
          </label>

          <label v-if="isRegisterMode" class="field-block">
            <span class="field-label">确认密码</span>
            <input
              v-model="registerForm.confirmPassword"
              class="app-input"
              :type="passwordVisible ? 'text' : 'password'"
              autocomplete="new-password"
              placeholder="再次输入密码"
            />
          </label>

          <label class="checkbox-row">
            <input v-model="passwordVisible" type="checkbox" />
            <span>显示密码</span>
          </label>

          <div v-if="errorMessage" class="inline-error">
            <span>{{ errorMessage }}</span>
            <button type="button" @click="errorMessage = ''">关闭</button>
          </div>

          <div class="login-actions">
            <AppButton type="submit" size="lg" :disabled="submitting || !canSubmit">
              {{ submitButtonText }}
            </AppButton>
            <button type="button" class="text-action" @click="toggleMode">
              {{ isRegisterMode ? '已有账号？去登录' : '没有账号？去注册' }}
            </button>
          </div>
        </form>
      </AppCard>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { loginUser, registerUser } from '@/api/user'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginForm = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  realName: '',
  username: '',
  password: '',
  confirmPassword: '',
  role: 'STUDENT',
})

const mode = ref('login')
const passwordVisible = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const isRegisterMode = computed(() => mode.value === 'register')
const activeForm = computed(() => (isRegisterMode.value ? registerForm : loginForm))

const canSubmit = computed(() => {
  if (isRegisterMode.value) {
    return Boolean(
      registerForm.realName &&
        registerForm.username &&
        registerForm.password &&
        registerForm.confirmPassword &&
        registerForm.role,
    )
  }

  return Boolean(loginForm.username && loginForm.password)
})

const submitButtonText = computed(() => {
  if (submitting.value) {
    return isRegisterMode.value ? '注册中...' : '登录中...'
  }
  return isRegisterMode.value ? '注册并进入系统' : '进入系统'
})

function setMode(nextMode) {
  mode.value = nextMode
  errorMessage.value = ''
}

function toggleMode() {
  setMode(isRegisterMode.value ? 'login' : 'register')
}

async function handleSubmit() {
  if (!canSubmit.value || submitting.value) {
    return
  }

  if (isRegisterMode.value && registerForm.password !== registerForm.confirmPassword) {
    errorMessage.value = '两次输入的密码不一致。'
    return
  }

  submitting.value = true
  errorMessage.value = ''

  try {
    const response = isRegisterMode.value
      ? await registerUser({
          username: registerForm.username,
          password: registerForm.password,
          realName: registerForm.realName,
          role: registerForm.role,
        })
      : await loginUser({
          username: loginForm.username,
          password: loginForm.password,
        })

    authStore.applySession(response.data)
    const redirectTarget =
      typeof route.query.redirect === 'string' && route.query.redirect
        ? route.query.redirect
        : '/classroom'
    await router.replace(redirectTarget)
  } catch (error) {
    errorMessage.value = getErrorMessage(
      error,
      isRegisterMode.value ? '注册失败，请稍后重试。' : '登录失败，请稍后重试。',
    )
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  padding: 2rem 1.25rem;
  background:
    radial-gradient(circle at top left, rgba(14, 90, 224, 0.18), transparent 30%),
    radial-gradient(circle at bottom right, rgba(24, 126, 168, 0.16), transparent 28%),
    linear-gradient(180deg, #f5f8ff 0%, #edf4ff 100%);
}

.login-shell {
  width: min(1120px, 100%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(360px, 0.92fr);
  gap: 1.5rem;
  align-items: stretch;
  min-height: calc(100vh - 4rem);
}

.login-hero,
.login-card {
  min-height: 40rem;
}

.login-hero {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 3rem;
  border-radius: 2rem;
  border: 1px solid rgba(112, 126, 180, 0.14);
  background:
    radial-gradient(circle at top left, rgba(14, 90, 224, 0.16), transparent 32%),
    radial-gradient(circle at bottom right, rgba(24, 126, 168, 0.16), transparent 30%),
    rgba(255, 255, 255, 0.86);
  box-shadow: var(--shadow-lg);
}

.login-hero h1 {
  margin: 0.9rem 0 1rem;
  font-size: clamp(2.6rem, 4.5vw, 4.2rem);
  line-height: 1.04;
  letter-spacing: -0.04em;
}

.login-hero p {
  max-width: 34rem;
  margin: 0;
  color: var(--text-secondary);
  font-size: 1.02rem;
  line-height: 1.9;
}

.login-highlights {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 2rem;
}

.highlight-item {
  padding: 1rem 1.05rem;
  border-radius: 1.2rem;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(118, 129, 178, 0.14);
}

.highlight-item strong {
  display: block;
  margin-bottom: 0.45rem;
  font-size: 1rem;
}

.highlight-item span {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.75;
}

.login-card {
  display: flex;
  flex-direction: column;
  gap: 1.35rem;
  padding: 2rem;
}

.login-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.login-card__header h2 {
  margin: 0.6rem 0 0;
  font-size: clamp(1.8rem, 3vw, 2.6rem);
  letter-spacing: -0.03em;
}

.login-badge {
  display: inline-flex;
  align-items: center;
  min-height: 2.35rem;
  padding: 0.35rem 1rem;
  border-radius: 999px;
  background: rgba(90, 121, 255, 0.1);
  color: #2559da;
  font-size: var(--font-size-sm);
  font-weight: 700;
}

.mode-switch,
.role-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.mode-switch__item,
.role-switch__item {
  min-height: 4rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1rem 1.1rem;
  border-radius: 1.4rem;
  border: 1px solid rgba(115, 128, 171, 0.14);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform var(--transition-base),
    border-color var(--transition-base),
    box-shadow var(--transition-base),
    background var(--transition-base);
}

.mode-switch__item:hover,
.mode-switch__item.active,
.role-switch__item:hover,
.role-switch__item.active {
  transform: translateY(-2px);
  border-color: rgba(37, 89, 218, 0.22);
  background: rgba(244, 247, 255, 0.96);
  box-shadow: 0 18px 30px rgba(65, 99, 179, 0.12);
}

.login-form {
  display: flex;
  flex-direction: column;
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

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.inline-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: 1rem;
  color: #ba3657;
  font-size: var(--font-size-sm);
  background: rgba(230, 84, 106, 0.08);
}

.inline-error button,
.text-action {
  color: inherit;
  font-weight: 700;
  cursor: pointer;
}

.login-actions {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  margin-top: 0.25rem;
}

.login-actions :deep(.app-button) {
  width: 100%;
}

.text-action {
  align-self: center;
  color: var(--primary-color);
  font-size: var(--font-size-sm);
}

@media (max-width: 960px) {
  .login-shell {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .login-hero,
  .login-card {
    min-height: auto;
  }

  .login-hero {
    padding: 2rem;
  }
}

@media (max-width: 640px) {
  .login-page {
    padding-inline: 0.85rem;
  }

  .login-highlights,
  .mode-switch,
  .role-switch {
    grid-template-columns: 1fr;
  }

  .login-card {
    padding: 1.35rem;
  }

  .login-card__header {
    flex-direction: column;
  }
}
</style>
