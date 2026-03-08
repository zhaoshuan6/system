#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库模型定义（按照设计文档）

表结构：
  - video_metadata   : 视频元数据
  - keyframes        : 关键帧
  - detected_objects : 检测到的人物目标
  - trajectory       : 人物轨迹
"""

import numpy as np
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Float,
    String, DateTime, ForeignKey, LargeBinary, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


# ================================================================
#  video_metadata 视频元数据表
# ================================================================
class VideoMetadata(Base):
    __tablename__ = "video_metadata"

    video_id   = Column(Integer, primary_key=True, autoincrement=True, comment="视频ID")
    file_path  = Column(Text, nullable=False,   comment="文件路径")
    duration   = Column(Float, nullable=True,   comment="视频时长（秒）")
    camera_id  = Column(Integer, nullable=True, comment="摄像头ID")
    created_at = Column(DateTime, default=datetime.utcnow)

    keyframes    = relationship("KeyFrame",   back_populates="video", cascade="all, delete-orphan")
    trajectories = relationship("Trajectory", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<VideoMetadata video_id={self.video_id}>"


# ================================================================
#  keyframes 关键帧表
# ================================================================
class KeyFrame(Base):
    __tablename__ = "keyframes"

    frame_id     = Column(Integer, primary_key=True, autoincrement=True, comment="帧ID")
    video_id     = Column(Integer, ForeignKey("video_metadata.video_id", ondelete="CASCADE"),
                          nullable=False, comment="所属视频ID")
    frame_time   = Column(Float, nullable=False, comment="帧时间（秒）")
    frame_path   = Column(Text, nullable=False,  comment="帧图片路径")
    clip_feature = Column(LargeBinary, nullable=True, comment="整帧CLIP特征向量（512维，用于文字搜图）")

    video   = relationship("VideoMetadata", back_populates="keyframes")
    objects = relationship("DetectedObject", back_populates="frame", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KeyFrame frame_id={self.frame_id} video_id={self.video_id} t={self.frame_time:.1f}s>"


# ================================================================
#  detected_objects 检测到的人物目标表
# ================================================================
class DetectedObject(Base):
    __tablename__ = "detected_objects"

    object_id    = Column(Integer, primary_key=True, autoincrement=True, comment="检测对象唯一ID")
    frame_id     = Column(Integer, ForeignKey("keyframes.frame_id", ondelete="CASCADE"),
                          nullable=False, comment="所在帧ID")
    bbox_x       = Column(Integer, nullable=False, comment="边界框左上角x坐标")
    bbox_y       = Column(Integer, nullable=False, comment="边界框左上角y坐标")
    bbox_w       = Column(Integer, nullable=False, comment="边界框宽度")
    bbox_h       = Column(Integer, nullable=False, comment="边界框高度")
    confidence   = Column(Float,   nullable=False, comment="YOLOv8检测置信度")
    clip_feature = Column(LargeBinary, nullable=False, comment="人物裁剪CLIP特征向量（512维，用于以图搜图）")

    frame = relationship("KeyFrame", back_populates="objects")

    # ----------------------------------------------------------------
    #  特征向量序列化工具
    # ----------------------------------------------------------------
    @staticmethod
    def encode_feature(feature: np.ndarray) -> bytes:
        """numpy array (512,) → bytes 存入数据库"""
        return feature.astype(np.float32).tobytes()

    @staticmethod
    def decode_feature(blob: bytes) -> np.ndarray:
        """bytes → numpy array (512,) 从数据库读出"""
        return np.frombuffer(blob, dtype=np.float32).copy()

    def get_feature(self) -> np.ndarray:
        return self.decode_feature(self.clip_feature)

    def __repr__(self):
        return f"<DetectedObject object_id={self.object_id} frame_id={self.frame_id} conf={self.confidence:.2f}>"


# ================================================================
#  trajectory 人物轨迹表
# ================================================================
class Trajectory(Base):
    __tablename__ = "trajectory"

    person_id       = Column(Integer, primary_key=True, autoincrement=True, comment="人物ID")
    video_id        = Column(Integer, ForeignKey("video_metadata.video_id", ondelete="CASCADE"),
                             nullable=False, comment="视频ID")
    timestamp       = Column(Float,       nullable=False, comment="时间戳（秒）")
    camera_location = Column(String(255), nullable=True,  comment="摄像机位置描述")

    video = relationship("VideoMetadata", back_populates="trajectories")

    def __repr__(self):
        return f"<Trajectory person_id={self.person_id} ts={self.timestamp:.1f}s loc={self.camera_location}>"
