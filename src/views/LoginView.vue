<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { invoke } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import { version } from '../../package.json'

const router = useRouter()
const account = ref('')
const loggingIn = ref(false)
const updateUrl = ref('')
const latestVersion = ref('')
const MOBILE_RE = /^1\d{10}$/
const LAST_MOBILE_KEY = 'resume_genie_last_mobile'

function persistLastMobile() {
  const v = account.value.trim()
  if (!v) return
  try {
    localStorage.setItem(LAST_MOBILE_KEY, v)
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  try {
    const saved = localStorage.getItem(LAST_MOBILE_KEY)
    if (saved) account.value = saved
  } catch {
    /* ignore */
  }
  try {
    const resp = await invoke<{ code: number; data: { hasUpdate: boolean; ossUrl: string; latestVersion: string } }>(
      'check_version',
      { currentVersion: version }
    )
    if (resp?.data?.hasUpdate && resp.data.ossUrl) {
      updateUrl.value = resp.data.ossUrl
      latestVersion.value = resp.data.latestVersion ?? ''
    }
  } catch {
    // 版本检查失败不影响正常使用
  }
})

async function openUpdate() {
  if (updateUrl.value) {
    await openUrl(updateUrl.value)
  }
}

async function handleLogin() {
  const input = account.value.trim()
  if (!input) {
    ElMessage.error('请输入手机号')
    return
  }
  if (!MOBILE_RE.test(input)) {
    ElMessage.error('请输入11位手机号')
    return
  }
  if (loggingIn.value) return
  loggingIn.value = true
  try {
    const resp = await invoke<{ code: number; msg: string; data: number }>(
      'verify_mobile_account',
      { mobile: input }
    )
    console.log('verify response:', resp)
    if (resp?.data === 1) {
      persistLastMobile()
      router.push('/dashboard')
      return
    }
    ElMessage.error('无效账号，请检查后重试')
  } catch (error) {
    ElMessage.error('登录校验失败，请稍后重试')
  } finally {
    loggingIn.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h2 class="title">欢迎使用AI简历精灵</h2>
      <p class="subtitle">您尚未登录，请先登录</p>

      <el-input
        v-model="account"
        placeholder="请输入11位手机号"
        size="large"
        autocomplete="tel"
        @blur="persistLastMobile"
        @keyup.enter="handleLogin"
      />

      <el-button
        type="primary"
        size="large"
        class="login-btn"
        :loading="loggingIn"
        @click="handleLogin"
      >
        登 录
      </el-button>

      <p class="version">
        当前版本:{{ version }}<a
          v-if="updateUrl"
          href="#"
          class="version-update"
          @click.prevent="openUpdate"
        >（最新版本:{{ latestVersion }}）</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f7fa;
}

.login-card {
  width: 320px;
  padding: 40px 32px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: #999;
  margin: 0;
}

.login-btn {
  width: 100%;
  background: linear-gradient(135deg, #a78bfa, #6366f1);
  border: none;
  font-size: 16px;
  letter-spacing: 4px;
}

.version {
  font-size: 12px;
  color: #bbb;
  margin: 0;
}

.version-update {
  color: #6366f1;
  cursor: pointer;
  text-decoration: underline;
}
</style>
