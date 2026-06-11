<script setup lang="ts">
import Navbar from "@/components/layout/Navbar.vue";
import Sidebar from "@/components/layout/Sidebar.vue";
import TagsView from "@/components/layout/TagsView.vue";
</script>

<template>
  <div class="layout">
    <Sidebar />
    <div class="main">
      <Navbar />
      <TagsView />
      <main class="content">
        <router-view v-slot="{ Component, route }">
          <transition name="page" mode="out-in" appear>
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  background: var(--swu-bg);
}
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.content {
  flex: 1;
  overflow: auto;
  padding: 18px 22px;
}
</style>
