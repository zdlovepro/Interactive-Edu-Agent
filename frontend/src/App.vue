<template>
  <div class="app-shell">
    <header v-if="!isAuthPage" class="app-header">
      <div class="page-shell header-inner">
        <RouterLink class="brand" to="/">
          <span class="brand-mark" aria-hidden="true">I</span>
          <div class="brand-copy">
            <strong>IEA 智能教学助手</strong>
            <span>Interactive-Edu-Agent</span>
          </div>
        </RouterLink>

        <nav class="header-nav" aria-label="主导航">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-link"
            :class="{ active: isNavActive(item) }"
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="header-user">
          <div class="header-user__meta">
            <span class="role-pill" :class="{ teacher: authStore.isTeacher, student: authStore.isStudent }">
              {{ roleLabel }}
            </span>
            <div>
              <strong>{{ authStore.displayName }}</strong>
              <span>{{ authStore.user?.username }}</span>
            </div>
          </div>

          <button type="button" class="logout-button" @click="handleLogout">退出</button>
        </div>
      </div>
    </header>

    <main :class="['app-main', { 'app-main--auth': isAuthPage }]">
      <router-view v-slot="{ Component }">
        <transition name="fade-up" mode="out-in">
          <component :is="Component" :key="$route.fullPath" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getUserProfile, logoutUser } from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

onMounted(() => {
  authStore.restore()
  if (authStore.token && !authStore.user) {
    getUserProfile()
      .then(response => {
        authStore.updateProfile(response.data)
      })
      .catch(() => {
        authStore.clearSession()
        router.replace('/login')
      })
  }
})

const isAuthPage = computed(() => route.name === 'Login')

const navItems = computed(() => [
  { label: '首页', to: '/' },
  { label: '导入中心', to: '/imports' },
  { label: authStore.isTeacher ? '我的课程' : '课堂资源', to: '/classroom' },
  { label: '个人中心', to: '/profile' },
])

const roleLabel = computed(() => (authStore.isTeacher ? '教师' : '学生'))

function isNavActive(item) {
  if (item.to === '/') {
    return route.path === '/'
  }

  if (item.to === '/imports') {
    return route.path.startsWith('/imports')
  }

  if (item.to === '/classroom') {
    return (
      route.path.startsWith('/classroom') ||
      route.path.startsWith('/courseware/') ||
      route.path.startsWith('/lecture/') ||
      route.path.startsWith('/script/') ||
      route.path.startsWith('/resources/')
    )
  }

  if (item.to === '/profile') {
    return route.path.startsWith('/profile') || route.path.startsWith('/mine')
  }

  return route.path.startsWith(item.to)
}

async function handleLogout() {
  try {
    await logoutUser()
  } catch {
    // Local session cleanup is still sufficient here.
  }

  authStore.clearSession()
  await router.replace('/login')
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(138, 150, 185, 0.14);
  background: rgba(249, 251, 255, 0.82);
  backdrop-filter: blur(16px);
}

.app-header::after {
  content: '';
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(14, 90, 224, 0.2), transparent);
}

.header-inner {
  min-height: 5rem;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 1rem;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.85rem;
}

.brand-mark {
  width: 2.5rem;
  height: 2.5rem;
  display: inline-grid;
  place-items: center;
  border-radius: 0.95rem;
  background:
    linear-gradient(135deg, rgba(14, 90, 224, 1), rgba(24, 126, 168, 0.92)),
    #ffffff;
  box-shadow: 0 16px 30px rgba(14, 90, 224, 0.24);
  overflow: hidden;
  color: #ffffff;
  font-size: 1.6rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0.02em;
}

.brand-copy strong {
  display: block;
  color: var(--text-primary);
  font-size: 1rem;
  letter-spacing: -0.01em;
}

.brand-copy span {
  display: block;
  margin-top: 0.2rem;
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

.header-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.nav-link {
  min-height: 2.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.6rem 0.95rem;
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 600;
  transition:
    color var(--transition-base),
    background var(--transition-base),
    box-shadow var(--transition-base);
}

.nav-link:hover {
  color: var(--text-primary);
  background: rgba(14, 90, 224, 0.07);
}

.nav-link.active {
  color: var(--primary-color);
  background: rgba(14, 90, 224, 0.11);
  box-shadow: inset 0 0 0 1px rgba(14, 90, 224, 0.12);
}

.header-user {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.header-user__meta {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}

.header-user__meta strong {
  display: block;
  font-size: var(--font-size-sm);
}

.header-user__meta span:last-child {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.role-pill {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.role-pill.teacher {
  color: #b15f1c;
  background: rgba(255, 186, 56, 0.14);
}

.role-pill.student {
  color: var(--primary-color);
  background: rgba(14, 90, 224, 0.08);
}

.logout-button {
  min-height: 2.25rem;
  padding: 0.5rem 0.8rem;
  border-radius: 999px;
  border: 1px solid rgba(136, 147, 184, 0.16);
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
}

.logout-button:hover {
  color: var(--text-primary);
}

.app-main {
  padding: 0 0 3rem;
}

.app-main--auth {
  padding: 0;
}

@media (max-width: 1080px) {
  .header-inner {
    grid-template-columns: 1fr;
    align-items: flex-start;
    padding-top: 0.9rem;
    padding-bottom: 0.9rem;
  }

  .header-nav {
    width: 100%;
    justify-content: flex-start;
  }

  .header-user {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .header-user {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-user__meta {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
