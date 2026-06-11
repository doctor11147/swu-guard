<!-- 参考来源: skills/art-design-pro/src/views/index -->
<script setup lang="ts">
import { zhCN } from "@/i18n/zh-CN";
</script>

<template>
  <header class="brand-header">
    <div class="brand-lockup">
      <img src="/brand/swu-logo.png" alt="西南大学校徽" class="brand-mark" />
      <h1>{{ zhCN.home.brand }}</h1>
    </div>
  </header>
</template>

<style scoped>
.brand-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.brand-mark {
  width: 40px;
  height: 40px;
  object-fit: contain;
  flex: 0 0 auto;
}

h1 {
  margin: 0;
  color: var(--xw-primary);
  font-size: clamp(20px, 3.4vw, 30px);
  font-weight: 700;
  line-height: 40px;
  letter-spacing: 0;
}

@media (max-width: 520px) {
  .brand-lockup {
    align-items: center;
  }

  .brand-mark {
    width: 36px;
    height: 36px;
  }

  h1 {
    line-height: 36px;
  }
}
</style>
