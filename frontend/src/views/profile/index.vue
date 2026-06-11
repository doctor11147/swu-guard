<script setup lang="ts">
/** 个人中心 · 信息卡 + 修改密码。 */
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Lock } from "@element-plus/icons-vue";

import { authApi } from "@/api/auth";
import DataCard from "@/components/common/DataCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

onMounted(async () => {
  if (!auth.user) await auth.fetchMe();
});

const roleLabel: Record<string, string> = {
  superadmin: "超级管理员", admin: "管理员", viewer: "只读",
};

const pwdForm = reactive({
  old_password: "",
  new_password: "",
  confirm: "",
});
const formRef = ref<FormInstance>();
const submitting = ref(false);

const rules: FormRules = {
  old_password: [{ required: true, message: "请输入旧密码", trigger: "blur" }],
  new_password: [
    { required: true, message: "请输入新密码", trigger: "blur" },
    { min: 8, max: 64, message: "新密码长度 8-64", trigger: "blur" },
  ],
  confirm: [
    { required: true, message: "请确认新密码", trigger: "blur" },
    {
      validator: (_r, v, cb) => {
        if (v !== pwdForm.new_password) cb(new Error("两次输入不一致"));
        else cb();
      },
      trigger: "blur",
    },
  ],
};

const strength = computed(() => {
  const v = pwdForm.new_password;
  if (!v) return { score: 0, label: "" };
  let s = 0;
  if (v.length >= 8) s++;
  if (/[A-Z]/.test(v)) s++;
  if (/[a-z]/.test(v)) s++;
  if (/[0-9]/.test(v)) s++;
  if (/[^A-Za-z0-9]/.test(v)) s++;
  return {
    score: s,
    label: ["很弱", "弱", "中", "强", "强", "极强"][s] ?? "",
  };
});

async function submit() {
  if (!formRef.value) return;
  await formRef.value.validate(async (ok) => {
    if (!ok) return;
    submitting.value = true;
    try {
      await authApi.changePassword(pwdForm.old_password, pwdForm.new_password);
      ElMessage.success("密码已更新，下次登录请用新密码");
      pwdForm.old_password = "";
      pwdForm.new_password = "";
      pwdForm.confirm = "";
    } finally {
      submitting.value = false;
    }
  });
}
</script>

<template>
  <div>
    <PageHeader title="个人中心" subtitle="账户信息 / 修改密码" />

    <div class="grid">
      <DataCard>
        <template #header><span class="head">基本信息</span></template>
        <div class="hero">
          <div class="avatar-big">
            {{ (auth.user?.name || auth.user?.username || "?").slice(0, 1) }}
          </div>
          <div>
            <div class="name">{{ auth.user?.name || "—" }}</div>
            <div class="sub">
              <el-tag size="small" effect="light">
                {{ roleLabel[auth.role] || auth.role }}
              </el-tag>
              <span class="mono">@{{ auth.user?.username }}</span>
            </div>
          </div>
        </div>

        <el-descriptions :column="1" border class="desc">
          <el-descriptions-item label="用户名">{{ auth.user?.username }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ auth.user?.name || "—" }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ auth.user?.email || "—" }}</el-descriptions-item>
          <el-descriptions-item label="角色">{{ roleLabel[auth.role] || auth.role }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="auth.user?.is_active ? 'success' : 'danger'">
              {{ auth.user?.is_active ? "正常" : "已禁用" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最近登录">
            {{ auth.user?.last_login_at?.replace("T", " ").slice(0, 19) || "—" }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ auth.user?.created_at?.replace("T", " ").slice(0, 19) || "—" }}
          </el-descriptions-item>
        </el-descriptions>
      </DataCard>

      <DataCard>
        <template #header>
          <span class="head">修改密码</span>
          <span class="dim">bcrypt $2b$12 · 推荐 8-16 位含字母数字符号</span>
        </template>
        <el-form
          ref="formRef" :model="pwdForm" :rules="rules"
          label-width="80px" size="default"
        >
          <el-form-item label="旧密码" prop="old_password">
            <el-input
              v-model="pwdForm.old_password" type="password"
              show-password autocomplete="current-password"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input
              v-model="pwdForm.new_password" type="password"
              show-password autocomplete="new-password"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
            <div v-if="pwdForm.new_password" class="strength">
              <div class="bar">
                <div
                  v-for="i in 5" :key="i"
                  :class="['seg', i <= strength.score && `s-${strength.score}`]"
                />
              </div>
              <span class="strength-label">强度：{{ strength.label }}</span>
            </div>
          </el-form-item>
          <el-form-item label="确认" prop="confirm">
            <el-input
              v-model="pwdForm.confirm" type="password"
              show-password autocomplete="new-password"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="submitting" @click="submit">
              更新密码
            </el-button>
          </el-form-item>
        </el-form>
      </DataCard>
    </div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 1024px) { .grid { grid-template-columns: 1fr; } }

.head { font-weight: 600; }
.dim { font-size: 12px; color: var(--swu-text-3); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--swu-text-3); font-size: 13px; }

.hero { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.avatar-big {
  width: 64px; height: 64px;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  color: #fff; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 28px; font-weight: 600;
  box-shadow: 0 4px 12px rgba(0, 61, 122, 0.32);
}
.name { font-size: 20px; font-weight: 600; }
.sub { display: flex; gap: 10px; align-items: center; margin-top: 4px; }

.strength { margin-top: 8px; display: flex; align-items: center; gap: 10px; font-size: 11px; }
.bar { display: flex; gap: 3px; flex: 1; }
.seg {
  height: 4px; flex: 1;
  background: var(--swu-divider);
  border-radius: 2px;
  transition: background 0.18s ease;
}
.seg.s-1 { background: #F5222D; }
.seg.s-2 { background: #FAAD14; }
.seg.s-3 { background: #FAAD14; }
.seg.s-4 { background: #52C41A; }
.seg.s-5 { background: var(--swu-blue); }
.strength-label { color: var(--swu-text-3); }
</style>
