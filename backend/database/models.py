#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库模型定义

表结构：
  - users            : 用户表（超级管理员 / 普通管理员）
  - video_metadata   : 视频元数据
  - keyframes        : 关键帧
  - detected_objects : 检测到的人物目标
  - trajectory       : 人物轨迹
"""

import hashlib
import numpy as np
from datetime import datetime
from sqlalchemy import (
    Column, Integer, Float, String,
    DateTime, ForeignKey, LargeBinary, Text, Boolean
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ================================================================
#  users 用户表
# ================================================================
class User(Base):
    __tablename__ = "users"

    user_id    = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String(64),  nullable=False, unique=True, comment="用户名")
    password   = Column(String(128), nullable=False, comment="密码（SHA256哈希）")
    role       = Column(String(16),  nullable=False, default="admin",
                        comment="角色：superuser / admin")
    is_active  = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(64), nullable=True, comment="创建者用户名")

    # 密保问题（仅超级管理员使用）
    secret_q1  = Column(String(128), nullable=True, comment="密保问题1答案（哈希）")
    secret_q2  = Column(String(128), nullable=True, comment="密保问题2答案（哈希）")

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()

    def check_password(self, password: str) -> bool:
        return self.password == self.hash_password(password)

    def check_secret(self, answer1: str, answer2: str) -> bool:
        """验证密保答案"""
        a1 = self.hash_password(answer1.strip())
        a2 = self.hash_password(answer2.strip())
        return self.secret_q1 == a1 and self.secret_q2 == a2

    def to_dict(self, show_path=True):
        return {
            "user_id":    self.user_id,
            "username":   self.username,
            "role":       self.role,
            "is_active":  self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }

    def __repr__(self):
        return f"<User {self.username} role={self.role}>"


# ================================================================
#  video_metadata 视频元数据表
# ================================================================
class VideoMetadata(Base):
    __tablename__ = "video_metadata"

    video_id   = Column(Integer, primary_key=True, autoincrement=True)
    file_path  = Column(Text,    nullable=False, comment="文件路径")
    duration   = Column(Float,   nullable=True,  comment="视频时长（秒）")
    camera_id  = Column(Integer, nullable=True,  comment="摄像头ID")
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

    frame_id     = Column(Integer, primary_key=True, autoincrement=True)
    video_id     = Column(Integer, ForeignKey("video_metadata.video_id", ondelete="CASCADE"),
                          nullable=False)
    frame_time   = Column(Float,   nullable=False, comment="帧时间（秒）")
    frame_path   = Column(Text,    nullable=False, comment="帧图片路径")
    clip_feature = Column(LargeBinary, nullable=True, comment="整帧CLIP特征（512维）")

    video   = relationship("VideoMetadata", back_populates="keyframes")
    objects = relationship("DetectedObject", back_populates="frame", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KeyFrame frame_id={self.frame_id} t={self.frame_time:.1f}s>"


# ================================================================
#  detected_objects 检测到的人物目标表
# ================================================================
class DetectedObject(Base):
    __tablename__ = "detected_objects"

    object_id    = Column(Integer, primary_key=True, autoincrement=True)
    frame_id     = Column(Integer, ForeignKey("keyframes.frame_id", ondelete="CASCADE"),
                          nullable=False)
    bbox_x       = Column(Integer, nullable=False)
    bbox_y       = Column(Integer, nullable=False)
    bbox_w       = Column(Integer, nullable=False)
    bbox_h       = Column(Integer, nullable=False)
    confidence   = Column(Float,   nullable=False)
    clip_feature = Column(LargeBinary, nullable=False, comment="人物裁剪CLIP特征（512维）")

    frame = relationship("KeyFrame", back_populates="objects")

    @staticmethod
    def encode_feature(feature: np.ndarray) -> bytes:
        return feature.astype(np.float32).tobytes()

    @staticmethod
    def decode_feature(blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32).copy()

    def get_feature(self) -> np.ndarray:
        return self.decode_feature(self.clip_feature)

    def __repr__(self):
        return f"<DetectedObject object_id={self.object_id} conf={self.confidence:.2f}>"


# ================================================================
#  trajectory 人物轨迹表
# ================================================================
class Trajectory(Base):
    __tablename__ = "trajectory"

    person_id       = Column(Integer, primary_key=True, autoincrement=True)
    video_id        = Column(Integer, ForeignKey("video_metadata.video_id", ondelete="CASCADE"),
                             nullable=False)
    timestamp       = Column(Float,       nullable=False)
    camera_location = Column(String(255), nullable=True)

    video = relationship("VideoMetadata", back_populates="trajectories")

    def __repr__(self):
        return f"<Trajectory person_id={self.person_id} ts={self.timestamp:.1f}s>"


# ================================================================
#  search_history 搜索历史表
# ================================================================
class SearchHistory(Base):
    __tablename__ = "search_history"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, nullable=False, comment="操作用户ID")
    username     = Column(String(64), nullable=False, comment="操作用户名")
    search_type  = Column(String(16), nullable=False, comment="搜索类型: text/image/trajectory")
    query_text   = Column(Text, nullable=True, comment="文字搜索内容")
    query_image  = Column(Text, nullable=True, comment="图片搜索时保存的图片路径")
    result_count = Column(Integer, default=0, comment="返回结果数量")
    created_at   = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":           self.id,
            "user_id":      self.user_id,
            "username":     self.username,
            "search_type":  self.search_type,
            "query_text":   self.query_text,
            "query_image":  self.query_image,
            "result_count": self.result_count,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SearchHistory id={self.id} type={self.search_type} user={self.username}>"
