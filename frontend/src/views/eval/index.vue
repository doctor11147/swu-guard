<script setup lang="ts">
import PageHeader from "@/components/common/PageHeader.vue";
import EmbeddingScatter from "./components/EmbeddingScatter.vue";
</script>

<template>
  <div class="eval-page">
    <PageHeader
      title="嵌入投影"
      subtitle="基于已注册人脸的 512 维 EdgeFace 特征，展示同一身份样本聚合、不同身份分离的结构。"
    />

    <EmbeddingScatter />
  </div>
</template>

<style scoped>
.eval-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  animation: eval-enter 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes eval-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
