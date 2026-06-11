<div align="center">

# 西小卫 · SWU-Guard

**西南大学校园人脸识别门禁系统**

西南大学计算机与信息科学学院 软件学院 · 大三学年设计项目

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?logo=mysql&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)

<img src="img/首页.jpg" width="85%" alt="系统首页">

</div>

---

## 简介

本项目面向高校校园多身份、高流量的出入场景，以本校：西南大学（北碚校区）为例，将 **检测 → 对齐 → 活体 → 质量 → 嵌入 → 检索** 六阶段识别链路与完整的门禁业务后台集成在一套可部署系统中。期望为同类型工作起到一定的参考借鉴价值。

## 功能特性

- 🔍 **六阶段识别链路**：SCRFD 检测、五点对齐、MiniFAS 静默活体、CR-FIQA 质量门控、EdgeFace 特征提取、FAISS 1:N 检索，纯 CPU 实时运行
- 🏛 **多角色后台**：超级管理员 / 管理员 / 门卫 / 只读四类角色，七门七卫、一门一卫的管辖收敛
- 🧾 **访客业务闭环**：自助登记 → 人脸采集 → 时段预约 → 后台审批 → 有效期内刷脸通行
- 📊 **通行审计**：全量识别日志携带阈值快照，支持组合筛选与 CSV 导出
- 🖥 **实时监控与数据大屏**：WebSocket 流式识别、性能观测面板、全屏可视化驾驶舱
- 🌦 **环境自适应**：VLM 环境感知 + 天气佐证，阈值安全边界
- 🧭 **嵌入投影**：512 维特征降维可视化，直观检查类内聚合与类间分离
- ⚙️ **阈值热更新**：识别参数集中配置，修改即生效且全程留痕

## 界面预览

| | |
|:---:|:---:|
| <img src="img/门禁识别.jpg" alt="门禁识别"> 无人值守刷脸识别 | <img src="img/驾驶舱.jpg" alt="数据大屏"> 全屏数据大屏 |
| <img src="img/仪表盘.png" alt="仪表盘"> 管理端仪表盘 | <img src="img/实时监控性能.jpg" alt="性能观测"> 识别性能观测 |
| <img src="img/VLM.png" alt="环境自适应"> 环境自适应控制 | <img src="img/嵌入投影.jpg" alt="嵌入投影"> 嵌入空间投影 |
| <img src="img/访客信息录入.jpg" alt="访客通道"> 访客自助通道 | <img src="img/门禁管理.jpg" alt="门禁管理"> 门禁节点管理 |

## 技术栈

| 层 | 技术 |
|---|---|
| 算法 | PyTorch · ONNX Runtime · InsightFace(SCRFD) · EdgeFace · MiniFAS · CR-FIQA · FAISS |
| 后端 | FastAPI · SQLAlchemy(async) · Alembic · MySQL · JWT + bcrypt · WebSocket/SSE |
| 前端 | Vue 3 · TypeScript · Vite · Element Plus · Pinia · ECharts · Tailwind CSS |

## 快速开始

**环境要求**：Python 3.10（Conda）· Node.js 18+ 与 pnpm · MySQL 8.0+，内存建议 8GB 及以上，普通 USB 摄像头即可。

```bash
git clone https://github.com/DokiforU/swu-guard.git
cd swu-guard
```

**1. 初始化数据库**

```bash
mysql -uroot -p < scripts/schema.sql
# 创建应用账户并授权，将连接串写入 .env 的 FACE_DB_URL
```

**2. 启动后端**

```bash
conda env create -f app/environment.yml
conda activate face
cp .env.example .env          # 配置 FACE_DB_URL 与 FACE_JWT_SECRET
alembic -c alembic.ini stamp 0006_visitor_cross_day
python -m app.scripts.seed_admin --password '<管理员密码>'
python -m app.scripts.seed_guards --password '<门卫密码>'
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**3. 启动前端**

```bash
cd frontend
pnpm install
pnpm dev
```

访问：管理后台 `http://localhost:5173` · API 文档 `http://localhost:8000/api/docs`

**平台说明**

- **macOS / Linux**：依赖经 Homebrew / apt 安装，生产可用 systemd 守护后端服务
- **Windows**：命令与上述一致（PowerShell 执行），MySQL 导入路径使用正斜杠，服务化可用 NSSM 包装
- EdgeFace、MiniFAS、CR-FIQA 上游仓库与权重经 `scripts/setup_third_party.sh`（Windows 使用 `setup_third_party.ps1`）拉取，模型资产说明见 [MODEL_MANIFEST.md](MODEL_MANIFEST.md)；SCRFD 检测包首次运行自动下载，离线环境请提前拷贝；存在 CUDA / MPS 时自动启用加速，否则回退 CPU

**生产部署**：`pnpm build` 后由后端进程直接托管静态产物，或置于 Nginx 之后反向代理（WebSocket 路径需开启协议升级）；受 FAISS 进程内对象约束，写入频繁场景建议单 worker 运行。

## 致谢

本项目基于以下优秀的开源工作构建，特此致谢：

| 项目 | 用途 |
|---|---|
| [InsightFace](https://github.com/deepinsight/insightface) | SCRFD 人脸检测与五点对齐 |
| [EdgeFace](https://github.com/otroshi/edgeface) | 轻量人脸特征提取模型 |
| [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) | MiniFAS 静默活体检测 |
| [CR-FIQA](https://github.com/fdbtrs/CR-FIQA) | 人脸图像质量评估 |
| [FAISS](https://github.com/facebookresearch/faiss) | 高维向量索引与 1:N 检索 |
| [FastAPI](https://github.com/fastapi/fastapi) / [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) / [Alembic](https://github.com/sqlalchemy/alembic) | 异步后端框架与数据持久化 |
| [Vue](https://github.com/vuejs/core) / [Vite](https://github.com/vitejs/vite) / [Pinia](https://github.com/vuejs/pinia) | 前端框架与工程化 |
| [Element Plus](https://github.com/element-plus/element-plus) / [ECharts](https://github.com/apache/echarts) / [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) | UI 组件与可视化 |
| [art-design-pro](https://github.com/Daymychen/art-design-pro) / [soybean-admin](https://github.com/soybeanjs/soybean-admin) / [vue-element-plus-admin](https://github.com/kailong321200875/vue-element-plus-admin) / [vue-pure-admin](https://github.com/pure-admin/vue-pure-admin) | 管理后台界面设计参考 |
| [Open-Meteo](https://open-meteo.com) | 环境自适应模块的开放天气数据 |

完整的第三方声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [licenses/](licenses) 目录。

## 其他说明

本项目为课程学年设计成果，仅供学习与交流使用。