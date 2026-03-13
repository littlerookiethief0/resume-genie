<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

function navigateTo(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="layout">
    <!-- 左侧导航 -->
    <div class="sidebar">
      <div class="logo">
        <img src="../assets/logo.png" class="logo-icon" />
        <span>简历精灵</span>
      </div>

      <div class="menu">
        <div
          class="menu-item"
          :class="{ active: route.path === '/dashboard/wake' }"
          @click="navigateTo('/dashboard/wake')"
        >
          AI简历唤醒
        </div>
        <div
          class="menu-item"
          :class="{ active: route.path === '/dashboard/parse' }"
          @click="navigateTo('/dashboard/parse')"
        >
          简历解析及保存
        </div>
      </div>
    </div>

    <!-- 右侧内容区 -->
    <div class="content">
      <router-view />
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background: #f5f7fa;
  overflow: hidden;
}

.sidebar {
  width: 180px;
  background: #fff;
  display: flex;
  flex-direction: column;
  padding: 20px 0;
  box-shadow: 2px 0 8px rgba(0,0,0,0.06);
  flex-shrink: 0;
  height: 100%;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px 24px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  border-bottom: 1px solid #f0f0f0;
}

.logo-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
}

.menu {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.menu-item {
  padding: 12px 20px;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  border-radius: 6px;
  margin: 0 8px;
  transition: all 0.2s;
}

.menu-item:hover {
  background: #f5f0ff;
  color: #6366f1;
}

.menu-item.active {
  background: #f5f0ff;
  color: #6366f1;
  font-weight: 500;
}

.content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  min-height: 0;
  min-width: 0;
}
</style>