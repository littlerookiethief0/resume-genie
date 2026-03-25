<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { ElMessage } from 'element-plus'
import { loadAutoParseAfterWake, saveAutoParseAfterWake } from '../composables/useAutoParseAfterWake'

interface Account {
  name: string
  phone: string
  lastParseTime: string
}

interface Site {
  id: string
  name: string
  logo: string
  timeFilter: number
  downloadDir: string
  isRunning: boolean
  accounts: Account[]
}

const autoParseEnabled = ref(loadAutoParseAfterWake())
watch(autoParseEnabled, (v) => saveAutoParseAfterWake(v))

const sites = ref<Site[]>([
  {
    id: 'boss',
    name: 'BOSS直聘',
    logo: new URL('../assets/boss.png', import.meta.url).href,
    timeFilter: 7,
    downloadDir: './boss_resume',
    isRunning: false,
    accounts: []
  },
  {
    id: 'liepin',
    name: '猎聘',
    logo: new URL('../assets/liepin.png', import.meta.url).href,
    timeFilter: 7,
    downloadDir: './liepin_resume',
    isRunning: false,
    accounts: []
  },
  {
    id: 'zhilian',
    name: '智联招聘',
    logo: new URL('../assets/zhilian.png', import.meta.url).href,
    timeFilter: 7,
    downloadDir: './zhilian_resume',
    isRunning: false,
    accounts: []
  },
  {
    id: 'qiancheng',
    name: '前程无忧',
    logo: new URL('../assets/qcwy.png', import.meta.url).href,
    timeFilter: 7,
    downloadDir: './qiancheng_resume',
    isRunning: false,
    accounts: []
  }
])

let unlisten: any = null
let unlistenData: any = null

onMounted(async () => {
  unlisten = await listen('parse_script_finished', (event: any) => {
    const [siteId, success] = event.payload
    const site = sites.value.find(s => s.id === siteId)
    if (site) {
      site.isRunning = false
      if (success) {
        ElMessage.success(`${site.name} 解析完成`)
      } else {
        ElMessage.warning(`${site.name} 解析已停止`)
      }
    }
  })

  unlistenData = await listen('parse_resume_data', (event: any) => {
    const [siteId, jsonStr] = event.payload
    try {
      const data = JSON.parse(jsonStr)
      const site = sites.value.find(s => s.id === siteId)
      if (site) {
        const now = new Date()
        const timeStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
        site.accounts.unshift({ name: data.name, phone: data.phone, lastParseTime: timeStr })
        if (site.accounts.length > 20) {
          site.accounts = site.accounts.slice(0, 20)
        }
      }
    } catch (e) {
      console.error('Failed to parse resume data:', e)
    }
  })
})

onUnmounted(() => {
  if (unlisten) {
    unlisten()
  }
  if (unlistenData) {
    unlistenData()
  }
})

async function openDirectory(path: string) {
  try {
    await invoke('open_directory', { path })
  } catch (error) {
    ElMessage.error('打开目录失败: ' + String(error))
  }
}

async function handleParse(site: any) {
  site.isRunning = true
  ElMessage.info(`开始解析 ${site.name}`)
  try {
    await invoke('run_parse_script', {
      siteId: site.id,
      days: site.timeFilter
    })
  } catch (error) {
    site.isRunning = false
    ElMessage.error(`${site.name} 解析失败: ${error}`)
  }
}

async function handleStop(site: any) {
  try {
    await invoke('stop_parse_script')
    site.isRunning = false
    ElMessage.info(`已停止 ${site.name} 解析`)
  } catch (error) {
    ElMessage.error(`停止失败: ${error}`)
  }
}
</script>

<template>
  <div class="parse-page">
    <h2 class="page-title">解析与保存</h2>
    <p class="page-desc">
      您登录网站后，由程序自动将网站中求职者主投的简历和您下载的简历自动解析及存入您的RCN平台私有人才库中。
    </p>

    <div class="auto-switch">
      <span class="switch-label">唤醒后自动解析</span>
      <el-switch v-model="autoParseEnabled" />
    </div>

    <div class="site-list">
      <div class="list-header">
        <span>网站</span>
        <span>最近解析时间</span>
        <span>时间过滤</span>
        <span>下载目录</span>
        <span class="header-action">操作</span>
      </div>

      <div v-for="site in sites" :key="site.id" class="site-row">
        <div class="site-name">
          <img :src="site.logo" class="site-logo" />
          <span>{{ site.name }}</span>
        </div>
        <div class="accounts">
          <div v-for="(account, index) in site.accounts" :key="index" class="account-item">
            <span class="account-name">{{ account.name }}</span>
            <span class="account-phone">{{ account.phone }}</span>
            <span class="account-time">{{ account.lastParseTime }}</span>
          </div>
        </div>
        <div class="time-filter">
          <el-input-number
            v-model="site.timeFilter"
            :min="1"
            :max="365"
            size="small"
            controls-position="right"
          />
          <span style="margin-left: 8px; font-size: 12px; color: #999">天内</span>
        </div>
        <div class="download-dir">
          <span class="dir-path" @click="openDirectory(site.downloadDir)">简历目录</span>
        </div>
        <div class="action">
          <el-button v-if="!site.isRunning" link type="primary" @click="handleParse(site)">开始</el-button>
          <el-button v-else link type="danger" @click="handleStop(site)">停止</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.parse-page {
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
  margin: 0 0 20px;
  line-height: 1.6;
}

.auto-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #fff;
  border-radius: 10px;
  padding: 16px 24px;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.switch-label {
  font-size: 14px;
  color: #333;
}

.site-list {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  flex: 1;
}

.list-header {
  display: grid;
  grid-template-columns: 1.2fr 1.5fr 1fr 1fr 0.8fr;
  padding: 12px 24px;
  font-size: 13px;
  color: #999;
  border-bottom: 1px solid #f0f0f0;
}

.header-action {
  text-align: right;
}

.site-row {
  display: grid;
  grid-template-columns: 1.2fr 1.5fr 1fr 1fr 0.8fr;
  padding: 16px 24px;
  align-items: center;
  border-bottom: 1px solid #f5f5f5;
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

.accounts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.account-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.account-name {
  color: #333;
  font-weight: 500;
  white-space: nowrap;
  min-width: 80px;
}

.account-phone {
  color: #555;
  white-space: nowrap;
  min-width: 110px;
}

.account-time {
  color: #999;
  white-space: nowrap;
}

.time-filter {
  display: flex;
  align-items: center;
}

.download-dir {
  display: flex;
  align-items: center;
}

.dir-path {
  font-size: 12px;
  color: #409eff;
  cursor: pointer;
  text-decoration: underline;
}

.dir-path:hover {
  color: #66b1ff;
}

.action {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
</style>