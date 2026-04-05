# 视频人物检索系统

基于多模态特征的监控视频智能检索系统，支持文字搜图、以图搜图、时空轨迹追踪等功能。

## 项目信息

| | |
|---|---|
| **学生** | 赵栓 (2022112559) |
| **专业** | 计算机科学与技术 |
| **指导老师** | 朱石磊 工程师 |

## 硬件环境

| 组件 | 规格 |
|------|------|
| CPU | AMD Ryzen 7 9700X |
| GPU | NVIDIA RTX 5080 (16GB VRAM) |
| 内存 | 32GB DDR5-6000 |

## 技术栈

### 前端
- React 18 + Vite
- Ant Design 5（UI 组件库）
- HTML5 Canvas（轨迹动画绘制）

### 后端
- Python Flask + Flask-CORS
- PyJWT（用户认证）
- SQLAlchemy ORM

### AI 模型
- **CLIP ViT-B/32**（OpenAI）— 多模态特征提取，支持文字/图片跨模态检索
- **YOLOv8x**（Ultralytics）— 人物目标检测与裁剪

### 数据库 & 索引
- MySQL 8.0（结构化数据存储）
- FAISS IndexFlatIP（余弦相似度向量检索）

---

## 功能模块

### 实时监控
- 支持本地摄像头、RTSP 视频流、本地视频文件三种输入源
- 实时画面预览

### 文字搜图
- 用自然语言描述目标人物（支持中英文）
- CLIP 文本编码后在 FAISS 索引中检索
- 返回匹配视频及对应关键帧

### 以图搜图
- 上传目标人物图片
- YOLOv8x 自动检测并裁剪主要人物区域
- CLIP 图像编码后检索相似人物出现记录

### 时空轨迹追踪
- 上传目标人物图片，追踪其在所有摄像头的出现记录
- Canvas 动画展示人物在各摄像头间的移动轨迹
- 右侧时间线列出各节点详情及关键帧缩略图

### 数据管理
- 视频上传与处理（自动提取关键帧 → 检测人物 → 提取 CLIP 特征 → 入库）
- 查看已处理视频列表及详情
- 删除视频及关联数据
- 手动重建 FAISS 索引

### 搜索历史
- 自动记录每次搜索（类型、内容、结果数、操作用户、时间）
- 支持按类型筛选（文字搜索 / 图片搜索 / 轨迹追踪）
- 普通管理员只能查看自己的记录，超级管理员可查看所有人的记录
- 支持逐条删除和批量清空

### 用户管理（超级管理员）
- 创建 / 启用禁用 / 重置密码 / 删除普通管理员账号
- 通过密保问题重置超级管理员密码

---

## 项目结构

```
vedio_retrieval_system/
├── backend/
│   ├── api/
│   │   ├── app.py                  # Flask 应用入口，蓝图注册
│   │   └── routes/
│   │       ├── auth.py             # 认证与用户管理 API
│   │       ├── search.py           # 搜索 API（文字/图片/轨迹）
│   │       ├── data.py             # 数据管理 API
│   │       ├── monitor.py          # 实时监控 API
│   │       └── history.py          # 搜索历史 API
│   ├── database/
│   │   ├── db.py                   # 数据库连接与初始化
│   │   ├── models.py               # SQLAlchemy 数据模型
│   │   └── ingest.py               # 数据入库工具
│   ├── models/
│   │   └── feature_index.py        # FAISS 索引管理
│   └── preprocessing/
│       └── video_processor.py      # 视频处理（抽帧→检测→特征提取）
├── fronted/
│   └── src/
│       ├── App.jsx                 # 主布局与路由
│       ├── api.js                  # Axios 封装（含 JWT 拦截器）
│       └── pages/
│           ├── Login.jsx           # 登录 / 密码重置
│           ├── Monitor.jsx         # 实时监控
│           ├── TextSearch.jsx      # 文字搜图
│           ├── ImageSearch.jsx     # 以图搜图
│           ├── Trajectory.jsx      # 时空轨迹追踪
│           ├── DataManage.jsx      # 数据管理
│           ├── SearchHistory.jsx   # 搜索历史
│           └── UserManage.jsx      # 用户管理
├── data/
│   ├── videos/                     # 原始视频文件
│   ├── processed/                  # 关键帧图片
│   ├── uploads/                    # 上传文件临时目录
│   └── database/                   # FAISS 索引文件
├── config.py                       # 全局配置（数据库/服务器/安全）
├── run.py                          # 后端启动入口
├── start.bat                       # 一键启动脚本（Windows）
├── requirements.txt                # Python 依赖
└── yolov8x.pt                      # YOLOv8x 权重文件
```

---

## 数据库表结构

| 表名 | 说明 |
|------|------|
| `users` | 用户（超级管理员 / 普通管理员），含密保字段 |
| `video_metadata` | 视频元数据（路径、时长、摄像头ID） |
| `keyframes` | 关键帧（时间戳、图片路径、整帧 CLIP 特征） |
| `detected_objects` | 检测到的人物（BBox、CLIP 特征） |
| `trajectory` | 人物轨迹记录 |
| `search_history` | 搜索历史（类型、内容、结果数、操作用户） |

---

## 快速开始

### 1. 安装依赖

```bash
conda activate video_retrieval
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.py`，修改以下字段：

```python
# MySQL 连接
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "你的密码",
    "database": "video_retrieval",
}

# 安全配置（必须修改）
SECURITY_CONFIG = {
    "jwt_secret":          "修改为随机字符串",
    "superuser_secret_q1": "密保问题1的答案",
    "superuser_secret_q2": "密保问题2的答案",
}
```

### 3. 启动

```bash
# 方式一：双击
start.bat

# 方式二：命令行
python run.py
```

前端访问：http://localhost:5173
后端接口：http://localhost:5000

### 4. 默认账号

系统首次启动时自动创建超级管理员，**初始密码打印在后端日志中**（`logs/backend.log`），请登录后立即修改。

---

## API 接口总览

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/api/auth/login` | 登录，返回 JWT |
| 认证 | POST | `/api/auth/logout` | 登出 |
| 认证 | GET | `/api/auth/me` | 获取当前用户信息 |
| 认证 | POST | `/api/auth/reset_password` | 密保重置密码 |
| 用户管理 | GET | `/api/auth/users` | 用户列表（超管） |
| 用户管理 | POST | `/api/auth/users` | 创建管理员（超管） |
| 用户管理 | PUT | `/api/auth/users/<id>` | 修改用户（超管） |
| 用户管理 | DELETE | `/api/auth/users/<id>` | 删除用户（超管） |
| 搜索 | POST | `/api/search/text` | 文字搜图 |
| 搜索 | POST | `/api/search/image` | 以图搜图 |
| 搜索 | POST | `/api/search/trajectory` | 时空轨迹追踪 |
| 数据 | POST | `/api/data/upload` | 上传并处理视频 |
| 数据 | GET | `/api/data/videos` | 视频列表 |
| 数据 | DELETE | `/api/data/videos/<id>` | 删除视频 |
| 数据 | POST | `/api/data/rebuild_index` | 重建 FAISS 索引 |
| 历史 | GET | `/api/history/` | 搜索历史列表 |
| 历史 | DELETE | `/api/history/<id>` | 删除单条历史 |
| 历史 | DELETE | `/api/history/` | 清空历史 |
| 监控 | GET | `/api/monitor/stream` | 视频流（MJPEG） |

---

## 文档

- [开题报告](docs/开题报告.pdf)
- [答辩PPT](docs/答辩PPT.pptx)
