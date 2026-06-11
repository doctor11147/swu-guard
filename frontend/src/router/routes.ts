import type { RouteRecordRaw } from "vue-router";

/**
 * 路由总表（按业务域分组）。
 * - meta.title      : 标题/面包屑
 * - meta.icon       : 侧栏图标
 * - meta.group      : 侧栏分组键（main / data / system）
 * - meta.roles      : 可见角色（不填 = 全部已登录可见）
 * - meta.requiresAuth: 是否要登录
 * - meta.hidden     : 在侧栏隐藏
 * - meta.keepAlive  : 是否在多页签缓存
 */
export const routes: RouteRecordRaw[] = [
  // ─── 公开首页与门识别 ─────────────────────────────────────────
  {
    path: "/",
    name: "Home",
    component: () => import("@/pages/HomePage.vue"),
    meta: { title: "西小卫 · 西南大学校园人脸识别门禁系统", hidden: true },
  },
  {
    path: "/gates/:gateId/recognize",
    name: "GateRecognize",
    component: () => import("@/pages/GateRecognizePage.vue"),
    meta: { title: "刷脸识别", hidden: true },
  },
  {
    path: "/visitor",
    name: "VisitorPortal",
    component: () => import("@/pages/VisitorPortalPage.vue"),
    meta: { title: "访客通道", hidden: true },
  },

  // ─── 登录 ─────────────────────────────────────────────────────
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/login/index.vue"),
    meta: { title: "登录", hidden: true },
  },
  {
    path: "/",
    component: () => import("@/layouts/default.vue"),
    redirect: "/dashboard",
    meta: { requiresAuth: true },
    children: [
      // ─── 主面板 ───────────────────────────────────────────────────────────
      {
        path: "/dashboard",
        name: "Dashboard",
        component: () => import("@/views/dashboard/index.vue"),
        meta: {
          title: "仪表盘", icon: "Odometer", group: "main",
          requiresAuth: true, keepAlive: true,
        },
      },
      {
        path: "/live",
        name: "LiveMonitor",
        component: () => import("@/views/live/index.vue"),
        meta: {
          title: "实时监控", icon: "VideoCamera", group: "main",
          requiresAuth: true,
        },
      },

      // ─── 数据 ─────────────────────────────────────────────────────────────
      {
        path: "/persons",
        name: "Persons",
        component: () => import("@/views/persons/index.vue"),
        meta: {
          title: "人员管理", icon: "User", group: "data",
          requiresAuth: true, keepAlive: true,
          roles: ["superadmin", "admin"],
        },
      },
      {
        path: "/persons/capture",
        name: "FaceCapture",
        component: () => import("@/views/persons/capture.vue"),
        meta: {
          title: "人脸录入", icon: "Camera", group: "data",
          requiresAuth: true,
          roles: ["superadmin", "admin"],
        },
      },
      {
        path: "/persons/:id",
        name: "PersonDetail",
        component: () => import("@/views/persons/detail.vue"),
        meta: {
          title: "人员详情", hidden: true, requiresAuth: true,
          roles: ["superadmin", "admin"],
        },
      },
      {
        path: "/access-logs",
        name: "AccessLogs",
        component: () => import("@/views/access-logs/index.vue"),
        meta: {
          title: "通行记录", icon: "Document", group: "data",
          requiresAuth: true, keepAlive: true,
        },
      },
      {
        path: "/visitors",
        name: "VisitorAppointments",
        component: () => import("@/views/visitors/index.vue"),
        meta: {
          title: "访客审核", icon: "Calendar", group: "data",
          requiresAuth: true, keepAlive: true,
          roles: ["superadmin", "admin", "guard"],
        },
      },
      {
        path: "/gates",
        name: "Gates",
        component: () => import("@/views/gates/index.vue"),
        meta: {
          title: "门禁管理", icon: "OfficeBuilding", group: "data",
          requiresAuth: true,
        },
      },

      // ─── 系统 ─────────────────────────────────────────────────────────────
      {
        path: "/settings",
        name: "Settings",
        component: () => import("@/views/settings/index.vue"),
        meta: {
          title: "系统配置", icon: "Setting", group: "system",
          requiresAuth: true, roles: ["superadmin", "admin"],
        },
      },
      {
        path: "/system/adaptive",
        name: "Adaptive",
        component: () => import("@/views/system/adaptive/index.vue"),
        meta: {
          title: "环境自适应", icon: "Monitor", group: "system",
          requiresAuth: true, roles: ["superadmin", "admin"],
        },
      },
      {
        path: "/eval",
        name: "EmbeddingEval",
        component: () => import("@/views/eval/index.vue"),
        meta: {
          title: "嵌入投影", icon: "DataAnalysis", group: "system",
          requiresAuth: true, roles: ["superadmin", "admin"],
        },
      },
      {
        path: "/profile",
        name: "Profile",
        component: () => import("@/views/profile/index.vue"),
        meta: {
          title: "个人中心", icon: "Avatar", group: "system",
          requiresAuth: true,
        },
      },
    ],
  },
  // 大屏：独立全屏路由，不走默认布局
  {
    path: "/screen",
    name: "Screen",
    component: () => import("@/views/screen/index.vue"),
    meta: { title: "数据大屏", hidden: true, requiresAuth: true },
  },
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    component: () => import("@/views/error/404.vue"),
    meta: { title: "页面不存在", hidden: true },
  },
];

/** 分组定义（顺序即展示顺序）。 */
export const groupDefs: Array<{ key: string; label: string }> = [
  { key: "main",   label: "主面板" },
  { key: "data",   label: "数据" },
  { key: "system", label: "系统" },
];
