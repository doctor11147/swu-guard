import { createApp } from "vue";
import { createPinia } from "pinia";
import piniaPersistedstate from "pinia-plugin-persistedstate";
import * as ElIcons from "@element-plus/icons-vue";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";

import App from "./App.vue";
import router from "./router";
import "./styles/index.scss";

import { useAppStore } from "./stores/app";

const app = createApp(App);

// 全局注册所有 Element Plus 图标。
// 原因：unplugin-vue-components 的 ElementPlusResolver 只解析 el-* 组件，
// 不解析 @element-plus/icons-vue 里的 PascalCase 图标。模板里直接使用
// <DataLine /> / <User /> 这类标签需要全局注册才能解析。
for (const [name, comp] of Object.entries(ElIcons)) {
  app.component(name, comp as never);
}

const pinia = createPinia();
pinia.use(piniaPersistedstate);
app.use(pinia);
app.use(router);

// 同步暗黑模式（跨 reload）
useAppStore().syncDark();

app.mount("#app");
