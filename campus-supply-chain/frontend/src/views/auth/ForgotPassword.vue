<template>
  <div class="page">
    <h2>忘记密码</h2>
    <p>请联系系统管理员重置密码；若需临时进入，请使用登录页预置账号。</p>
    <router-link to="/login">返回登录</router-link>
  </div>
</template>

<style scoped lang="scss">
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  gap: 12px;
}
</style>
