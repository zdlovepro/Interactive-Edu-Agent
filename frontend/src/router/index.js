import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import { hasStoredSession } from '@/utils/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: {
      title: 'Home',
    },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: {
      title: 'Login',
      public: true,
    },
  },
  {
    path: '/imports',
    name: 'ImportCenter',
    component: () => import('../views/ImportCenterView.vue'),
    meta: {
      title: 'Import Center',
    },
  },
  {
    path: '/classroom',
    name: 'ClassroomHub',
    component: () => import('../views/ClassroomHubView.vue'),
    meta: {
      title: 'Classroom',
    },
  },
  {
    path: '/imports/upload',
    name: 'LocalUpload',
    component: () => import('../views/Upload.vue'),
    meta: {
      title: 'Local Upload',
    },
  },
  {
    path: '/imports/chaoxing',
    name: 'ChaoxingImport',
    component: () => import('../views/CourseResourceImportView.vue'),
    meta: {
      title: 'Chaoxing Import',
    },
  },
  {
    path: '/imports/url',
    name: 'UrlImport',
    component: () => import('../views/UrlImportView.vue'),
    meta: {
      title: 'URL Import',
    },
  },
  {
    path: '/courseware/:coursewareId',
    name: 'ResourceDetail',
    component: () => import('../views/ResourceDetailView.vue'),
    meta: {
      title: 'Courseware Detail',
    },
  },
  {
    path: '/lecture/:coursewareId',
    name: 'Lecture',
    component: () => import('../views/Lecture.vue'),
    meta: {
      title: 'Lecture',
    },
  },
  {
    path: '/script/:coursewareId',
    name: 'Script',
    component: () => import('../views/Script.vue'),
    meta: {
      title: 'Script',
    },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Mine.vue'),
    meta: {
      title: 'Profile',
    },
  },
  {
    path: '/resources',
    redirect: '/classroom',
  },
  {
    path: '/resources/:coursewareId',
    redirect: to => ({
      name: 'ResourceDetail',
      params: { coursewareId: to.params.coursewareId },
    }),
  },
  {
    path: '/resources/:coursewareId/lecture',
    redirect: to => ({
      name: 'Lecture',
      params: { coursewareId: to.params.coursewareId },
    }),
  },
  {
    path: '/resources/:coursewareId/script',
    redirect: to => ({
      name: 'Script',
      params: { coursewareId: to.params.coursewareId },
    }),
  },
  {
    path: '/courses',
    redirect: '/classroom',
  },
  {
    path: '/videos',
    redirect: '/classroom',
  },
  {
    path: '/video-assets',
    redirect: '/classroom',
  },
  {
    path: '/mine',
    redirect: '/profile',
  },
  {
    path: '/upload',
    redirect: '/imports/upload',
  },
  {
    path: '/course-resource-import',
    redirect: '/imports/chaoxing',
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
    meta: {
      title: 'Not Found',
      public: true,
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(to => {
  const appTitle = import.meta.env.VITE_APP_TITLE || 'Interactive-Edu-Agent'
  document.title = `${to.meta.title || 'Interactive-Edu-Agent'} - ${appTitle}`

  const isAuthenticated = hasStoredSession()
  const isPublicRoute = to.meta.public === true

  if (to.name === 'Login' && isAuthenticated) {
    return { name: 'ClassroomHub' }
  }

  if (!isPublicRoute && !isAuthenticated) {
    return {
      name: 'Login',
      query: { redirect: to.fullPath },
    }
  }

  return true
})

export default router
