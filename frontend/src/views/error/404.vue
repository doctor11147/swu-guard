<script setup lang="ts">
const router = useRouter();
</script>

<template>
  <div class="oops">
    <div class="card">
      <div class="num">404</div>
      <div class="msg">这扇门走错了</div>
      <p class="sub">页面不存在或已被移除。请检查地址，或回到西小卫主页。</p>
      <el-button type="primary" round @click="router.push('/')">回首页</el-button>
    </div>
  </div>
</template>

<style scoped>
.oops {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background:
    radial-gradient(60% 60% at 30% 30%, rgba(21,101,192,0.10) 0%, transparent 60%),
    var(--swu-bg);
}
.card { text-align: center; padding: 48px 64px; }
.num {
  font-size: 120px; font-weight: 700;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  letter-spacing: 0.04em;
}
.msg { font-size: 22px; font-weight: 600; color: var(--swu-text); margin-top: 12px; }
.sub { font-size: 14px; color: var(--swu-text-3); margin: 8px 0 24px; }
</style>
