<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { invoke } from '@tauri-apps/api/core'
import { version } from '../../package.json'

const router = useRouter()
const account = ref('')
const loggingIn = ref(false)
const MOBILE_RE = /^1\d{10}$/

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

      <p class="version">当前版本{{ version }}</p>
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
</style>
