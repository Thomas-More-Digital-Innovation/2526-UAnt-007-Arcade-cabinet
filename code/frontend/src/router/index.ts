import { createRouter, createWebHistory } from 'vue-router'
import Landing from '@/views/Landing.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: Landing
    }
  ]
})

export default router
