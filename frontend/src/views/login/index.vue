<script setup lang="ts">
/**
 * 登录页 · 双栏式（左品牌区 + 右表单）。
 * 设计灵感：
 *   - vue-pure-admin/src/views/login/index.vue 的双栏布局
 *   - soybean-admin 的渐变 + 浮动光斑装饰
 *   - SWU VIS 主色（深蓝 + 金）
 */
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Lock, User } from "@element-plus/icons-vue";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const formRef = ref<FormInstance>();
const form = reactive({
  username: "",
  password: "",
});
const loading = ref(false);

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

async function onSubmit() {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (!valid) return;
    loading.value = true;
    try {
      await auth.login(form.username, form.password);
      ElMessage.success(`欢迎回来，${auth.user?.name || form.username}`);
      const redirect = (route.query.redirect as string) || "/dashboard";
      router.replace(redirect);
    } catch {
      // 错误消息由 axios 拦截器统一弹出
    } finally {
      loading.value = false;
    }
  });
}

const today = new Date();

/** 系统能力卖点（替代"建校年/办学年数"等过度学校化的元素） */
const features = [
  { icon: "🛡️", label: "静默活体", desc: "MiniFAS 双模型集成" },
  { icon: "⚡",  label: "实时识别", desc: "200ms · CPU" },
  { icon: "🎯", label: "1:N 检索", desc: "FAISS 向量库" },
  { icon: "🔒", label: "JWT 鉴权", desc: "RBAC · bcrypt" },
];
</script>

<template>
  <div class="login-root">
    <!-- 浮动光斑装饰 -->
    <div class="orb orb-1" />
    <div class="orb orb-2" />
    <div class="orb orb-3" />

    <div class="login-card">
      <!-- 左：品牌区 -->
      <div class="brand">
        <div class="brand-bg" />
        <div class="brand-content">
          <div class="brand-top">
            <img src="/brand/swu-logo.png" alt="SWU" class="brand-logo" />
            <div>
              <div class="brand-name-zh">西南大学</div>
              <div class="brand-name-en">SOUTHWEST UNIVERSITY</div>
            </div>
          </div>

          <div class="brand-hero">
            <h1 class="motto product-motto">
              <span>西小卫：</span>
              <span>西南大学校园人脸识别门禁系统</span>
            </h1>
            <p class="spirit">数智赋能校园安全</p>
          </div>

          <div class="brand-footer">
            <div v-for="f in features" :key="f.label" class="feat">
              <div class="feat-emoji">{{ f.icon }}</div>
              <div>
                <div class="feat-label">{{ f.label }}</div>
                <div class="feat-desc">{{ f.desc }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：表单区 -->
      <div class="form-wrap">
        <div class="form-inner">
          <div class="form-head">
            <div class="form-title">欢迎登录</div>
            <div class="form-sub">西小卫 · 管理后台</div>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            size="large"
            @keyup.enter="onSubmit"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="用户名"
                clearable
              >
                <template #prefix>
                  <el-icon><User /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                show-password
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-button
              type="primary"
              size="large"
              class="submit-btn"
              :loading="loading"
              @click="onSubmit"
            >
              {{ loading ? "登录中..." : "进入系统" }}
            </el-button>
          </el-form>

          <div class="form-foot">
            <span>© {{ today.getFullYear() }} 西南大学计算机与信息科学学院 · 软件学院</span>
            <span class="dim">渝ICP 06005063号-4</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-root {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(60% 50% at 18% 32%, rgba(21, 101, 192, 0.18) 0%, transparent 60%),
    radial-gradient(50% 40% at 82% 70%, rgba(212, 175, 55, 0.12) 0%, transparent 60%),
    linear-gradient(135deg, #001A3D 0%, #002855 35%, #003D7A 100%);
  overflow: hidden;
  padding: 24px;
}

/* 浮动光斑（CSS-only） */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.55;
  pointer-events: none;
  animation: orb-float 12s ease-in-out infinite;
}
.orb-1 { width: 380px; height: 380px; background: #1565C0; top: -80px; left: -60px; }
.orb-2 { width: 280px; height: 280px; background: #D4AF37; bottom: -70px; right: 10%; animation-delay: 3s; }
.orb-3 { width: 220px; height: 220px; background: #B22222; top: 30%; right: -90px; animation-delay: 6s; opacity: 0.32; }

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0); }
  50%      { transform: translate(20px, -30px); }
}

.login-card {
  position: relative;
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-radius: 18px;
  box-shadow:
    0 20px 60px rgba(0, 26, 61, 0.45),
    0 0 0 1px rgba(255, 255, 255, 0.4) inset;
  overflow: hidden;
  animation: card-in 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* === 左：品牌区 === */
.brand {
  position: relative;
  color: #fff;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 600px;
  isolation: isolate;
}
.brand-bg {
  position: absolute; inset: 0;
  background:
    linear-gradient(155deg, #003D7A 0%, #002855 60%, #001A3D 100%),
    url("/brand/swu-logo.png") right -40px bottom -30px / 280px no-repeat;
  background-blend-mode: normal, soft-light;
  z-index: -1;
}
.brand-bg::after {
  content: "";
  position: absolute; inset: 0;
  background: url("/brand/swu-logo.png") center / 60% no-repeat;
  opacity: 0.04;
  filter: brightness(0) invert(1);
}

.brand-top {
  display: flex; align-items: center; gap: 14px;
}
.brand-logo {
  width: 48px; height: 48px; object-fit: contain;
  filter: drop-shadow(0 2px 6px rgba(0,0,0,0.25));
}
.brand-name-zh { font-size: 20px; font-weight: 600; letter-spacing: 0.04em; }
.brand-name-en { font-size: 11px; opacity: 0.7; letter-spacing: 0.18em; margin-top: 2px; }

.brand-content {
  min-height: 504px;
  display: flex;
  flex-direction: column;
}
.brand-hero {
  margin-top: 104px;
  margin-bottom: 0;
}
.motto {
  font-weight: 600;
  margin: 0;
  background: linear-gradient(180deg, #fff 0%, #B8C8DD 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 2px 24px rgba(255,255,255,0.12);
}
.product-motto {
  display: grid;
  gap: 12px;
}
.product-motto span {
  display: block;
}
.product-motto span:first-child {
  font-size: 46px;
  line-height: 1.1;
  letter-spacing: 0.04em;
}
.product-motto span:last-child {
  max-width: none;
  font-size: 26px;
  line-height: 1.28;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.spirit { margin-top: 24px; opacity: 0.78; font-size: 15px; letter-spacing: 0.04em; }

.brand-footer {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px 24px;
  margin-top: auto;
  margin-bottom: 18px;
  padding-top: 24px;
  border-top: 1px solid rgba(255,255,255,0.12);
}
.feat {
  display: flex; align-items: center; gap: 10px;
}
.feat-emoji { font-size: 20px; opacity: 0.92; }
.feat-label { font-size: 13px; font-weight: 600; letter-spacing: 0.04em; color: #fff; }
.feat-desc  { font-size: 12px; opacity: 0.58; margin-top: 2px; }

/* === 右：表单区 === */
.form-wrap {
  display: flex; align-items: center; justify-content: center;
  padding: 48px 40px;
  background: #fff;
}
.form-inner { width: 100%; max-width: 360px; }
.form-head { margin-bottom: 32px; }
.form-title { font-size: 26px; font-weight: 600; color: var(--swu-text); margin: 0; }
.form-sub   { font-size: 13px; color: var(--swu-text-3); margin-top: 6px; letter-spacing: 0.04em; }

.submit-btn {
  width: 100%;
  height: 44px;
  background: linear-gradient(135deg, #003D7A 0%, #1565C0 100%);
  border: none;
  font-weight: 500;
  letter-spacing: 0.08em;
  box-shadow: 0 4px 14px rgba(0, 61, 122, 0.32);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.submit-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 22px rgba(0, 61, 122, 0.42);
}

.form-foot {
  margin-top: 64px;
  display: flex; justify-content: space-between;
  font-size: 11px; color: var(--swu-text-3);
  letter-spacing: 0.04em;
}
.form-foot .dim { opacity: 0.65; }

/* 响应式：窄屏隐藏品牌区 */
@media (max-width: 880px) {
  .login-card { grid-template-columns: 1fr; max-width: 420px; }
  .brand { display: none; }
  .form-wrap { padding: 40px 28px; }
}

/* === 暗黑模式适配 === */
:global(html.dark) .login-card { background: rgba(17, 26, 46, 0.92); }
:global(html.dark) .form-wrap  { background: var(--swu-bg-elev); }
:global(html.dark) .form-title { color: var(--swu-text); }
</style>
