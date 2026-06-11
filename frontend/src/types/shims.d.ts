// Element Plus 的 locale 文件未提供 type，手动声明。
declare module "element-plus/dist/locale/zh-cn.mjs" {
  import type { Language } from "element-plus/es/locale";
  const locale: Language;
  export default locale;
}
declare module "element-plus/dist/locale/*.mjs" {
  import type { Language } from "element-plus/es/locale";
  const locale: Language;
  export default locale;
}
