import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: {
      title: '首页',
    },
  },
  {
    path: '/resources',
    name: 'ResourceLibrary',
    component: () => import('../views/Courses.vue'),
    meta: {
      title: '课件资源库',
    },
  },
  {
    path: '/resources/:coursewareId',
    name: 'ResourceDetail',
    component: () => import('../views/ResourceDetailView.vue'),
    meta: {
      title: '课件资源详情',
    },
  },
  {
    path: '/imports',
    name: 'ImportCenter',
    component: () => import('../views/ImportCenterView.vue'),
    meta: {
      title: '导入中心',
    },
  },
  {
    path: '/imports/upload',
    name: 'LocalUpload',
    component: () => import('../views/Upload.vue'),
    meta: {
      title: '本地上传',
    },
  },
  {
    path: '/imports/chaoxing',
    name: 'ChaoxingImport',
    component: () => import('../views/CourseResourceImportView.vue'),
    meta: {
      title: '从超星导入课件',
    },
  },
  {
    path: '/imports/url',
    name: 'UrlImport',
    component: () => import('../views/UrlImportView.vue'),
    meta: {
      title: '普通 URL 导入',
    },
  },
  {
    path: '/videos',
    name: 'VideoAssets',
    component: () => import('../views/VideoAssetsView.vue'),
    meta: {
      title: '视频资产与 HLS 播放',
    },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Mine.vue'),
    meta: {
      title: '个人中心',
    },
  },
  {
    path: '/resources/:coursewareId/lecture',
    name: 'Lecture',
    component: () => import('../views/Lecture.vue'),
    meta: {
      title: '互动课堂',
    },
  },
  {
    path: '/resources/:coursewareId/script',
    name: 'Script',
    component: () => import('../views/Script.vue'),
    meta: {
      title: '课件讲稿',
    },
  },
  {
    path: '/courses',
    redirect: '/resources',
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
    path: '/video-assets',
    redirect: '/videos',
  },
  {
    path: '/lecture/:coursewareId',
    redirect: to => ({
      name: 'Lecture',
      params: { coursewareId: to.params.coursewareId },
    }),
  },
  {
    path: '/script/:coursewareId',
    redirect: to => ({
      name: 'Script',
      params: { coursewareId: to.params.coursewareId },
    }),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
    meta: {
      title: '页面不存在',
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const appTitle = import.meta.env.VITE_APP_TITLE || 'Interactive-Edu-Agent'
  document.title = `${to.meta.title || 'Interactive-Edu-Agent'} - ${appTitle}`
  next()
})

export default router

