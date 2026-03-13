import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import MainLayout from '../layouts/MainLayout.vue'
import ResumeWakeView from '../views/ResumeWakeView.vue'
import ResumeParseView from '../views/ResumeParseView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/login'
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/dashboard',
      component: MainLayout,
      redirect: '/dashboard/wake',
      children: [
        {
          path: 'wake',
          name: 'wake',
          component: ResumeWakeView
        },
        {
          path: 'parse',
          name: 'parse',
          component: ResumeParseView
        }
      ]
    }
  ]
})

export default router