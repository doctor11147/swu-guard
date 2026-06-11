<script setup lang="ts">
/**
 * 管理员人脸录入 · 照片上传入口。
 * 参考 skills/vue-pure-admin 与 vue-element-plus-admin 的 Upload 交互：
 * 拖拽区域、图片类型/大小校验、选完即交给父组件统一入库，不在组件内调用 API。
 */
import { Picture, UploadFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import type { UploadFile, UploadInstance } from "element-plus";
import { onBeforeUnmount, ref } from "vue";

const emit = defineEmits<{
  (e: "add-files", files: File[]): void;
}>();

const uploadRef = ref<UploadInstance>();
const MAX_FILE_MB = 8;
const MAX_BATCH_FILES = 20;
const pendingFiles: File[] = [];
let flushTimer: number | undefined;

function isValidImage(file: File): boolean {
  if (!file.type.startsWith("image/")) {
    ElMessage.warning(`${file.name} 不是图片文件`);
    return false;
  }
  if (file.size / 1024 / 1024 > MAX_FILE_MB) {
    ElMessage.warning(`${file.name} 超过 ${MAX_FILE_MB}MB，请压缩后再上传`);
    return false;
  }
  return true;
}

function flushPendingFiles() {
  flushTimer = undefined;
  if (pendingFiles.length > MAX_BATCH_FILES) {
    ElMessage.warning(`单次最多添加 ${MAX_BATCH_FILES} 张照片`);
  }
  const files = pendingFiles.splice(0, MAX_BATCH_FILES);
  if (files.length) emit("add-files", files);
  pendingFiles.length = 0;
  uploadRef.value?.clearFiles();
}

function onChange(file: UploadFile) {
  if (file.raw && isValidImage(file.raw)) pendingFiles.push(file.raw);
  if (flushTimer !== undefined) window.clearTimeout(flushTimer);
  flushTimer = window.setTimeout(flushPendingFiles, 0);
}

onBeforeUnmount(() => {
  if (flushTimer !== undefined) window.clearTimeout(flushTimer);
  pendingFiles.length = 0;
});
</script>

<template>
  <el-upload
    ref="uploadRef"
    class="face-upload"
    drag
    multiple
    accept="image/*"
    :auto-upload="false"
    :show-file-list="false"
    :on-change="onChange"
  >
    <div class="upload-shell">
      <span class="upload-icon">
        <el-icon><UploadFilled /></el-icon>
      </span>
      <div class="upload-copy">
        <strong>上传照片</strong>
        <span>拖拽图片到此处，或点击选择近期清晰正脸照片</span>
      </div>
      <span class="upload-format">
        <el-icon><Picture /></el-icon>
        JPG / PNG / WebP
      </span>
    </div>
    <template #tip>
      <div class="upload-tip">
        上传照片会加入候选样本，提交后仍由后端执行人脸检测、活体检测、质量评分、SHA-256 去重和 FAISS 入库。
      </div>
    </template>
  </el-upload>
</template>

<style scoped>
.face-upload :deep(.el-upload) {
  width: 100%;
}

.face-upload :deep(.el-upload-dragger) {
  width: 100%;
  padding: 0;
  overflow: hidden;
  border: 1px dashed rgba(0, 61, 122, 0.24);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(0, 61, 122, 0.06), rgba(212, 175, 55, 0.05)),
    rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 24px rgba(0, 61, 122, 0.06);
  transition:
    border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.face-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--swu-blue);
  box-shadow: 0 12px 30px rgba(0, 61, 122, 0.12);
  transform: translateY(-1px);
}

.upload-shell {
  min-height: 92px;
  padding: 16px 18px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  text-align: left;
}

.upload-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
  background: linear-gradient(135deg, #003D7A, #1565C0);
  box-shadow: 0 10px 20px rgba(0, 61, 122, 0.18);
}

.upload-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.upload-copy strong {
  color: var(--swu-text);
  font-size: 15px;
  font-weight: 700;
}

.upload-copy span,
.upload-tip {
  color: var(--swu-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.upload-format {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 999px;
  color: var(--swu-blue);
  background: rgba(0, 61, 122, 0.08);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.upload-tip {
  margin-top: 8px;
}

@media (max-width: 720px) {
  .upload-shell {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .upload-format {
    grid-column: 1 / -1;
    justify-self: start;
  }
}
</style>
