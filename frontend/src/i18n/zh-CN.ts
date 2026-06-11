export const zhCN = {
  home: {
    brand: "西小卫 · 西南大学校园人脸识别门禁系统",
    gateCountAbnormal: "数据加载异常",
    gateLoading: "正在加载门禁数据",
    gateError: "门禁数据加载失败，请检查服务连接",
    adminLogin: "管理员登录",
    guardLogin: "门卫登录",
    visitorEntry: "访客通道",
    recognizeEntry: "进入识别",
    footer: "© 学年设计 · 西小卫 · 西南大学校园人脸识别门禁系统",
  },
  recognize: {
    titlePrefix: "正在识别",
    alignHint: "请将面部对准框内",
    start: "开始识别",
    retry: "重新识别",
    uploadFallback: "上传一张照片",
    cameraDenied: "无法开启摄像头，请授权后重试，或上传照片识别",
    unsupported: "当前浏览器不支持摄像头调用，请上传照片识别",
    loadingGate: "正在加载门禁信息",
    gateError: "门禁信息加载失败",
    todoAuto: "TODO: 自动识别模式",
  },
  result: {
    granted: "通行已允许",
    denied: "身份未识别，请重试或联系门卫",
    spoof: "检测到非活体，请勿使用照片/视频",
    network: "识别服务异常，请重试",
  },
} as const;

export type ZhCN = typeof zhCN;
