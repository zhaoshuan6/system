#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置文件 - 修改这里的数据库连接信息
"""

# ================================================================
#  MySQL 连接配置 - 只需要修改这里！
# ================================================================
MYSQL_CONFIG = {
    "host":     "127.0.0.1",
    "port":     3306,
    "user":     "root",
    "password": "123456",
    "database": "video_retrieval",      # ← 数据库名（会自动创建）
    "charset":  "utf8mb4",
}

# SQLAlchemy 连接字符串（自动从上面生成，不用改）
def get_db_url() -> str:
    c = MYSQL_CONFIG
    return (
        f"mysql+pymysql://{c['user']}:{c['password']}"
        f"@{c['host']}:{c['port']}/{c['database']}"
        f"?charset={c['charset']}"
    )

# ================================================================
#  FAISS 索引配置
# ================================================================
FAISS_CONFIG = {
    "index_path": "data/database/faiss.index",
    "meta_path":  "data/database/faiss.meta.pkl",
    "dim":        512,   # CLIP ViT-B/32 输出维度
}

# ================================================================
#  视频处理配置
# ================================================================
VIDEO_CONFIG = {
    "processed_dir":  "data/processed",
    "videos_dir":     "data/videos",
    "frame_interval": 10,    # 关键帧提取间隔（秒）
    "detect_conf":    0.3,   # YOLOv8 检测置信度阈值
}

# ================================================================
#  服务器配置
# ================================================================
SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": False,
}
