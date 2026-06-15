<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="page-shell header-inner">
        <RouterLink class="brand" to="/">
          <span class="brand-mark"></span>
          <div>
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
      </div>
    </header>

    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade-up" mode="out-in">
          <component :is="Component" :key="$route.fullPath" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { label: '首页', to: '/' },
  { label: '导入中心', to: '/imports' },
  { label: '课堂', to: '/classroom' },
  { label: '个人中心', to: '/profile' },
]

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
  background: linear-gradient(90deg, transparent, rgba(93, 104, 255, 0.2), transparent);
}

.header-inner {
  min-height: 5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  border-radius: 0.95rem;
  background:
    linear-gradient(135deg, rgba(95, 104, 255, 1), rgba(141, 91, 255, 0.92)),
    #ffffff;
  box-shadow: 0 14px 28px rgba(93, 104, 255, 0.26);
}

.brand strong {
  display: block;
  color: var(--text-primary);
  font-size: 1rem;
  letter-spacing: -0.01em;
}

.brand span {
  display: block;
  margin-top: 0.2rem;
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

.header-nav {
  display: flex;
  align-items: center;
  justify-content: flex-end;
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
  background: rgba(95, 104, 255, 0.07);
}

.nav-link.active {
  color: var(--primary-color);
  background: rgba(95, 104, 255, 0.11);
  box-shadow: inset 0 0 0 1px rgba(95, 104, 255, 0.12);
}

.app-main {
  padding: 0 0 3rem;
}

@media (max-width: 768px) {
  .header-inner {
    min-height: auto;
    flex-direction: column;
    align-items: flex-start;
    padding-top: 0.9rem;
    padding-bottom: 0.9rem;
  }

  .header-nav {
    width: 100%;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .nav-link {
    flex: 1;
    min-width: calc(25% - 0.4rem);
  }
}
</style>
