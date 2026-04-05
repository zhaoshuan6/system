# 视频检索系统

基于多模态特征的监控视频智能检索系统

## 项目信息


## 技术栈

### 前端
- React.js + Ant Design + ECharts

### 后端
- Python Flask
- PyTorch 2.10.0 + CUDA 13.0
- CLIP (多模态检索)
- YOLOv8 (人物检测)

### 数据库
- MySQL 8.0
- Faiss (向量检索)

### 硬件
- AMD Ryzen 7 9700X
- NVIDIA RTX 5080 (16GB)
- 32GB DDR5-6000

## 项目结构
```
video_retrieval_system/
├── backend/              # 后端代码
│   ├── preprocessing/   # 数据预处理
│   ├── models/          # AI模型
│   ├── database/        # 数据库操作
│   └── api/             # API接口
├── frontend/            # 前端代码（待开发）
├── data/                # 数据目录
│   ├── videos/         # 原始视频
│   ├── MOT17/          # MOT17数据集
│   └── processed/      # 处理结果
├── tests/               # 测试代码
└── docs/                # 文档
```

## 开发进度

- [x] Week 1: 环境搭建
- [x] Week 1: 视频预处理模块
- [ ] Week 2-3: 数据库设计
- [ ] Week 4-5: 后端API开发
- [ ] Week 6-8: 前端开发

## 快速开始

### 环境激活
```bash
conda activate video_retrieval
```

### 运行测试
```bash
# 环境验证
python final_check.py

# MOT17测试
python test_mot17.py
```

## 文档

- [开题报告](docs/开题报告.pdf)
- [答辩PPT](docs/答辩PPT.pptx)
