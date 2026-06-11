<script setup lang="ts">
/**
 * 人员编辑抽屉 · 新建 / 编辑 通用。
 * - 学号输入时实时调 /api/persons/parse-id 解析年级 + 院系代码（前端 helper）
 * - 学院下拉随学部联动
 */
import { ElMessage, type FormInstance, type FormRules } from "element-plus";

import { personsApi } from "@/api/persons";
import type { CollegeOut, FacultyOut, PersonOut, PersonRole } from "@/api/types";

const props = defineProps<{
  open: boolean;
  /** null = 新建；number = 编辑 */
  id: number | null;
  faculties: FacultyOut[];
  colleges: CollegeOut[];
}>();
const emit = defineEmits<{
  (e: "update:open", v: boolean): void;
  (e: "saved"): void;
}>();

const visible = computed({
  get: () => props.open,
  set: (v) => emit("update:open", v),
});

const formRef = ref<FormInstance>();
const saving = ref(false);
const facultyId = ref<number | null>(null);
const parsedHint = ref<string>("");

const form = reactive({
  external_id: "",
  name: "",
  role: "student" as PersonRole,
  college_id: null as number | null,
  major: "",
  class_code: "",
  enrollment_year: null as number | null,
  campus: "beibei" as const,
  dorm_zone: null as string | null,
  phone: "",
  email: "",
  note: "",
});

const filteredColleges = computed(() => {
  if (!facultyId.value) return props.colleges;
  return props.colleges.filter((c) => c.faculty_id === facultyId.value);
});

watch(() => form.college_id, (cid) => {
  // 选了学院自动联动学部
  if (!cid) return;
  const c = props.colleges.find((x) => x.id === cid);
  if (c?.faculty_id) facultyId.value = c.faculty_id;
});

const rules: FormRules = {
  external_id: [{ required: true, message: "请输入唯一标识", trigger: "blur" }],
  name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
  role: [{ required: true, message: "请选择身份", trigger: "change" }],
};

/* 唯一标识字段随 role 切换文案：
 *  - 学生（本科/研究生）→ 学号
 *  - 教师/职工        → 工号
 *  - 访客             → 身份证号
 */
const idLabel = computed(() => {
  switch (form.role) {
    case "visitor": return "身份证号";
    case "teacher":
    case "staff":   return "工号";
    default:        return "学号";
  }
});
const idPlaceholder = computed(() => {
  switch (form.role) {
    case "visitor":      return "18 位身份证号，例：500101200001019999";
    case "graduate":     return "10-15 位研究生学号";
    case "teacher":
    case "staff":        return "5-10 位工号";
    default:             return "例：222022326062999（本科 15 位）";
  }
});
const idHint = computed(() => {
  switch (form.role) {
    case "visitor":  return "前 17 位数字，末位数字或大写 X";
    case "graduate": return "研究生学号 10-15 位数字";
    case "teacher":  return "教师工号 5-10 位";
    case "staff":    return "职工工号 5-10 位";
    default:         return "本科生学号 15 位，以 22 开头";
  }
});

async function parseSid() {
  if (!form.external_id || form.external_id.length !== 15 || form.role !== "student") {
    parsedHint.value = "";
    return;
  }
  try {
    const r = await personsApi.parseId(form.external_id);
    if (r.valid) {
      parsedHint.value =
        `${r.type_name} · ${r.enrollment_year} 级 · 学院代码 ${r.college_code}`;
      // 自动填年份
      if (!form.enrollment_year) form.enrollment_year = r.enrollment_year ?? null;
      // 尝试按 college_code 匹配
      const c = props.colleges.find((x) => x.code === r.college_code);
      if (c && !form.college_id) form.college_id = c.id;
    } else {
      parsedHint.value = "";
    }
  } catch {
    parsedHint.value = "";
  }
}

async function loadForEdit() {
  if (props.id == null) return;
  const p: PersonOut = await personsApi.get(props.id);
  form.external_id = p.external_id;
  form.name = p.name;
  form.role = p.role as typeof form.role;
  form.college_id = p.college_id;
  form.major = p.major ?? "";
  form.class_code = p.class_code ?? "";
  form.enrollment_year = p.enrollment_year;
  form.campus = p.campus as typeof form.campus;
  form.dorm_zone = p.dorm_zone;
  form.phone = p.phone ?? "";
  form.email = p.email ?? "";
  form.note = p.note ?? "";
}

function resetForm() {
  facultyId.value = null;
  parsedHint.value = "";
  Object.assign(form, {
    external_id: "", name: "", role: "student",
    college_id: null, major: "", class_code: "",
    enrollment_year: null, campus: "beibei", dorm_zone: null,
    phone: "", email: "", note: "",
  });
}

watch(visible, (open) => {
  if (open) {
    resetForm();
    if (props.id != null) loadForEdit();
  }
});

async function save() {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (!valid) return;
    saving.value = true;
    try {
      const payload = { ...form };
      // 后端不允许某些空字段：清掉
      if (!payload.dorm_zone) (payload as Record<string, unknown>).dorm_zone = null;
      if (props.id == null) {
        await personsApi.create(payload as unknown as Record<string, unknown>);
        ElMessage.success("已创建");
      } else {
        // 更新时不能改 external_id；后端只允许部分字段
        const { external_id: _unused, ...rest } = payload;
        await personsApi.update(props.id, rest as unknown as Record<string, unknown>);
        ElMessage.success("已更新");
      }
      emit("saved");
    } finally {
      saving.value = false;
    }
  });
}
</script>

<template>
  <el-drawer
    v-model="visible"
    :title="id == null ? '新建人员' : `编辑人员 #${id}`"
    size="540px"
    destroy-on-close
  >
    <el-form
      ref="formRef" :model="form" :rules="rules"
      label-width="92px" size="default"
    >
      <el-form-item :label="idLabel" prop="external_id">
        <el-input
          v-model="form.external_id"
          :disabled="id != null"
          :placeholder="idPlaceholder"
          @blur="parseSid"
        />
        <div v-if="parsedHint" class="hint">{{ parsedHint }}</div>
        <div v-else class="hint-mute">{{ idHint }}</div>
      </el-form-item>
      <el-form-item label="姓名" prop="name">
        <el-input v-model="form.name" maxlength="32" />
      </el-form-item>
      <el-form-item label="身份" prop="role">
        <el-radio-group v-model="form.role">
          <el-radio-button value="student">本科生</el-radio-button>
          <el-radio-button value="graduate">研究生</el-radio-button>
          <el-radio-button value="teacher">教师</el-radio-button>
          <el-radio-button value="staff">职工</el-radio-button>
          <el-radio-button value="visitor">访客</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-divider content-position="left">归属</el-divider>

      <el-form-item label="学部">
        <el-select v-model="facultyId" placeholder="选择学部" clearable>
          <el-option v-for="f in faculties" :key="f.id" :label="f.name" :value="f.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="学院">
        <el-select v-model="form.college_id" placeholder="选择学院" clearable filterable>
          <el-option
            v-for="c in filteredColleges" :key="c.id"
            :label="c.name" :value="c.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="专业">
        <el-input v-model="form.major" placeholder="如：计算机科学与技术" />
      </el-form-item>
      <el-form-item label="班级">
        <el-input v-model="form.class_code" placeholder="如：2022级06班" />
      </el-form-item>
      <el-form-item label="入学年份">
        <el-input-number v-model="form.enrollment_year" :min="1900" :max="2100" controls-position="right" />
      </el-form-item>

      <el-divider content-position="left">校区 / 生活</el-divider>

      <el-form-item label="校区">
        <el-radio-group v-model="form.campus">
          <el-radio-button value="beibei">北碚校区</el-radio-button>
          <el-radio-button value="rongchang">荣昌校区</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="园区">
        <el-select v-model="form.dorm_zone" placeholder="可选" clearable>
          <el-option label="楠园" value="nan" />
          <el-option label="竹园" value="zhu" />
          <el-option label="梅园" value="mei" />
          <el-option label="李园" value="li" />
          <el-option label="橘园" value="ju" />
          <el-option label="桃园" value="tao" />
          <el-option label="杏园" value="xing" />
        </el-select>
      </el-form-item>

      <el-divider content-position="left">联系</el-divider>

      <el-form-item label="手机">
        <el-input v-model="form.phone" maxlength="20" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" maxlength="64" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.note" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ id == null ? "创建" : "保存" }}
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--swu-blue);
  background: var(--swu-blue-50);
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
}
.hint-mute {
  margin-top: 4px;
  font-size: 12px;
  color: var(--swu-text-3);
  line-height: 1.5;
}
.footer { text-align: right; }
</style>
