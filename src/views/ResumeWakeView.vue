<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { ElMessage } from 'element-plus'
import { loadAutoParseAfterWake } from '../composables/useAutoParseAfterWake'

const sites = ref([
  {
    id: 'boss',
    name: 'BOSS直聘',
    logo: new URL('../assets/boss.png', import.meta.url).href,
    status: 'idle',
    page: 0,
    maxPages: 100,
  },
  {
    id: 'liepin',
    name: '猎聘',
    logo: new URL('../assets/liepin.png', import.meta.url).href,
    status: 'idle',
    page: 0,
    maxPages: 100,
  },
  {
    id: 'zhilian',
    name: '智联招聘',
    logo: new URL('../assets/zhilian.png', import.meta.url).href,
    status: 'idle',
    page: 0,
    maxPages: 100,
  },
  {
    id: 'qiancheng',
    name: '前程无忧',
    logo: new URL('../assets/qcwy.png', import.meta.url).href,
    status: 'idle',
    page: 0,
    maxPages: 100,
  }
])

function getSiteById(id: string) {
  return sites.value.find((s) => s.id === id)
}

function getStatusText(status: string) {
  switch (status) {
    case 'running':
      return '正在唤醒中'
    case 'done':
      return '今日已唤醒'
    default:
      return '今日未唤醒'
  }
}

function getStatusColor(status: string) {
  switch (status) {
    case 'running':
      return '#e6a23c'
    case 'done':
      return '#67c23a'
    default:
      return '#999'
  }
}

const activeStep = ref(0)

let unlistenFinished: (() => void) | undefined
let unlistenStep: (() => void) | undefined
let unlistenPage: (() => void) | undefined

onMounted(async () => {
  unlistenFinished = await listen<[string, boolean, number | null]>('wake_script_finished', (event) => {
    const [siteId, success, code] = event.payload
    const site = getSiteById(siteId)
    if (!site) return
    site.status = 'idle'
    site.page = 0
    activeStep.value = 0
    if (code === -1) {
      ElMessage.warning(`${site.name} 已停止唤醒`)
    } else if (success) {
      site.status = 'done'
      ElMessage.success(`${site.name} 唤醒完成`)
    } else {
      ElMessage.error(`${site.name} 唤醒失败`)
    }
  })

  unlistenStep = await listen<[string, number]>('wake_step', (event) => {
    const [, step] = event.payload
    activeStep.value = step
  })

  unlistenPage = await listen<[string, number]>('wake_page', (event) => {
    const [siteId, page] = event.payload
    const site = getSiteById(siteId)
    if (!site) return
    site.page = page
  })
})

onUnmounted(() => {
  unlistenFinished?.()
  unlistenStep?.()
  unlistenPage?.()
})

async function handleAction(site: any) {
  if (site.status === 'running') {
    try {
      await invoke('stop_wake_script')
      site.status = 'idle'
    } catch (e) {
      ElMessage.error('停止失败: ' + String(e))
    }
    return
  }

  site.status = 'running'
  activeStep.value = 0
  site.page = 0
  ElMessage.info(`开始唤醒 ${site.name}`)

  try {
    await invoke('run_wake_script', {
      siteId: site.id,
      days: 7,
      autoParse: loadAutoParseAfterWake(),
      wakeMaxPages: site.maxPages || 5,
    })
  } catch (error) {
    site.status = 'idle'
    ElMessage.error(`${site.name} 启动失败: ${error}`)
  }
}
</script>

<template>
  <div class="wake-page">
    <h2 class="page-title">简历唤醒</h2>
    <p class="page-desc">
      简历精灵可自动比对您私有库中的简历在招聘网站的活跃状态，您只需选择目标网站完成登录，即自动为您唤醒简历
    </p>

    <!-- 警告提示 -->
    <div class="warning-bar">
      🔔 请注意：唤醒过程中，请勿在该招聘网站完成其他操作，以免影响结果准确性。
    </div>

    <!-- 步骤说明 -->
    <div class="steps-wrap">
      <el-steps :active="activeStep" align-center>
        <el-step title="登录网站" />
        <el-step title="检测唤醒条件" description="简历搜索条件" />
        <el-step title="开始唤醒" />
      </el-steps>
    </div>

    <!-- 网站列表 -->
    <div class="site-list">
      <div class="list-header">
        <span>网站</span>
        <span>唤醒状态</span>
        <span class="header-config">最大页数</span>
        <span class="header-action">操作</span>
      </div>

      <div v-for="site in sites" :key="site.id" class="site-row">
        <div class="site-name">
          <img :src="site.logo" class="site-logo" />
          <span>{{ site.name }}</span>
        </div>
        <span class="site-status" :style="{ color: getStatusColor(site.status) }">
          {{ getStatusText(site.status) }}
        </span>
        <span class="site-page">
          <el-input-number
            v-model="site.maxPages"
            class="site-maxpages-input"
            :min="1"
            :max="500"
            :step="1"
            size="small"
            controls-position="right"
            :disabled="site.status === 'running'"
          />
        </span>
        <div class="action">
          <el-button link type="primary" @click="handleAction(site)">
            {{ site.status === 'running' ? '停止唤醒' : '开始唤醒' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wake-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px;
}

.page-desc {
  font-size: 13px;
  color: #666;
  margin: 0 0 12px;
}

.config-label {
  font-size: 13px;
  color: #999;
  font-weight: 400;
}

.config-hint {
  font-size: 12px;
  color: #999;
}

.warning-bar {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 13px;
  color: #d48806;
  margin-bottom: 16px;
}

.steps-wrap {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  margin-bottom: 24px;
}

.site-list {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  flex: 1;
}

.list-header {
  display: grid;
  grid-template-columns: 1.1fr 1fr 320px 90px;
  padding: 12px 24px;
  font-size: 13px;
  color: #999;
  border-bottom: 1px solid #f0f0f0;
}

.header-config {
  text-align: left;
  white-space: nowrap;
}

.header-action {
  min-width: 56px;
  text-align: right;
}

.site-row {
  display: grid;
  grid-template-columns: 1.1fr 1fr 320px 90px;
  padding: 16px 24px;
  align-items: center;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.2s;
}

.site-row:last-child {
  border-bottom: none;
}

.site-row:hover {
  background: #fafafa;
}

.site-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.site-logo {
  width: 32px;
  height: 32px;
  object-fit: contain;
  border-radius: 6px;
}

.site-status {
  font-size: 14px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.site-page {
  display: inline-flex;
  justify-content: flex-start;
  align-items: center;
  white-space: nowrap;
  gap: 10px;
  width: 100%;
}

.site-maxpages-input {
  width: 120px;
}

.site-info {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
}

.action {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
</style>