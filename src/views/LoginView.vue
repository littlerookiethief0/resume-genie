<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { version } from '../../package.json'

const router = useRouter()
const account = ref('')
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h2 class="title">欢迎使用AI简历精灵</h2>
      <p class="subtitle">您尚未登录，请先登录</p>

      <el-input
        v-model="account"
        placeholder="请输入RCN平台账号"
        size="large"
        @keyup.enter="handleLogin"
      />

      <el-button
        type="primary"
        size="large"
        class="login-btn"
        @click="handleLogin"
      >
        登 录
      </el-button>

      <p class="version">当前版本{{ version }}</p>
    </div>
  </div>
</template>

<script lang="ts">
function handleLogin() {
  if (!account.value) {
    ElMessage.error('请输入RCN平台账号')
    return
  }
  if (account.value === 'root') {
    router.push('/dashboard')
    return
  }
  // 正常账号走正常登录逻辑（后面对接API）
  ElMessage.error('账号不存在，请检查后重试')
}
</script>

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