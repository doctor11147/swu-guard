import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    vue(),
    // Vue / Pinia / VueRouter / VueUse 函数自动导入
    AutoImport({
      imports: ["vue", "vue-router", "pinia", "@vueuse/core"],
      dts: "src/types/auto-imports.d.ts",
      resolvers: [ElementPlusResolver()],
      eslintrc: { enabled: true },
    }),
    // Element Plus 组件按需引入
    Components({
      dts: "src/types/components.d.ts",
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: "modern-compiler",
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // 后端：FastAPI on :8000
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    target: "es2022",
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // 按域拆 chunk，加载更顺
        manualChunks: {
          "vue-core": ["vue", "vue-router", "pinia", "@vueuse/core"],
          "ui": ["element-plus", "@element-plus/icons-vue"],
          "charts": ["echarts", "vue-echarts"],
        },
      },
    },
  },
});
