#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据入库模块
功能：将 video_processor 输出的 pickle 文件写入 MySQL 数据库，并构建 FAISS 索引

用法（命令行）：
    python -m backend.database.ingest \
        --pickle data/processed/MOT17-02-FRCNN/MOT17-02-FRCNN_processed.pkl \
        --video  data/videos/MOT17-02-FRCNN.mp4 \
        --camera_id 1 \
        --camera_location "图书馆门口"
"""

import sys
import pickle
import logging
import argparse
from pathlib import Path

import cv2
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_video_duration(video_path: str) -> float:
    """用 OpenCV 获取视频时长（秒）"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return total_frames / fps


def ingest(
    pickle_path: str,
    video_path: str = "",
    camera_id: int = 1,
    camera_location: str = "未知位置",
):
    """
    将 pickle 处理结果写入数据库，并重建 FAISS 索引

    Args:
        pickle_path:     video_processor 输出的 .pkl 文件
        video_path:      原始视频文件路径
        camera_id:       摄像头ID
        camera_location: 摄像头位置描述（如"图书馆门口"）
    """
    from backend.database.db import get_session
    from backend.database.models import VideoMetadata, KeyFrame, DetectedObject, Trajectory
    from backend.models.feature_index import FeatureIndex
    from config import FAISS_CONFIG

    pickle_path = Path(pickle_path)
    if not pickle_path.exists():
        raise FileNotFoundError(f"pickle 文件不存在: {pickle_path}")

    logger.info(f"读取处理结果: {pickle_path}")
    with open(pickle_path, "rb") as f:
        processed_data = pickle.load(f)

    logger.info(f"共 {len(processed_data)} 帧待入库")

    session = get_session()
    try:
        # ----------------------------------------------------------------
        # 1. 写入 video_metadata
        # ----------------------------------------------------------------
        duration = get_video_duration(video_path) if video_path else 0.0
        video_name = pickle_path.stem.replace("_processed", "")

        # 检查是否已存在（以文件路径为唯一标识）
        existing = session.query(VideoMetadata).filter_by(file_path=str(video_path)).first()
        if existing:
            logger.warning(f"视频已存在（video_id={existing.video_id}），跳过入库")
            return existing.video_id

        video_record = VideoMetadata(
            file_path=str(video_path) if video_path else str(pickle_path),
            duration=duration,
            camera_id=camera_id,
        )
        session.add(video_record)
        session.flush()  # 获取 video_id
        video_id = video_record.video_id
        logger.info(f"video_metadata 写入完成，video_id={video_id}")

        # ----------------------------------------------------------------
        # 2. 逐帧写入 keyframes + detected_objects
        # ----------------------------------------------------------------
        total_objects = 0

        for frame_data in processed_data:
            # 写整帧的 CLIP 特征（用于文字搜图）
            # video_processor 目前只存人物裁剪特征，整帧特征暂为 None
            kf = KeyFrame(
                video_id=video_id,
                frame_time=frame_data.get("timestamp", 0.0),
                frame_path=frame_data["frame_path"],
                clip_feature=None,  # Week 3 扩展：文字搜图时补全
            )
            session.add(kf)
            session.flush()  # 获取 frame_id

            for person in frame_data["persons"]:
                x1, y1, x2, y2 = person["bbox"]
                obj = DetectedObject(
                    frame_id=kf.frame_id,
                    bbox_x=x1,
                    bbox_y=y1,
                    bbox_w=x2 - x1,
                    bbox_h=y2 - y1,
                    confidence=person["confidence"],
                    clip_feature=DetectedObject.encode_feature(person["features"]),
                )
                session.add(obj)
                total_objects += 1

        # ----------------------------------------------------------------
        # 3. 写入 trajectory（每帧每个人物生成一条轨迹记录）
        # ----------------------------------------------------------------
        for frame_data in processed_data:
            if frame_data["persons"]:
                traj = Trajectory(
                    video_id=video_id,
                    timestamp=frame_data.get("timestamp", 0.0),
                    camera_location=camera_location,
                )
                session.add(traj)

        session.commit()
        logger.info(f"✅ 数据入库完成：{len(processed_data)} 帧，{total_objects} 个人物目标")

        # ----------------------------------------------------------------
        # 4. 重建 FAISS 索引
        # ----------------------------------------------------------------
        logger.info("重建 FAISS 索引...")
        index = FeatureIndex(
            dim=FAISS_CONFIG["dim"],
            index_path=FAISS_CONFIG["index_path"],
        )
        count = index.build_from_db(session)
        if count > 0:
            index.save()
            logger.info(f"✅ FAISS 索引重建完成，共 {count} 条向量")
        else:
            logger.warning("数据库中暂无特征向量，索引未保存")

        return video_id

    except Exception as e:
        session.rollback()
        logger.error(f"入库失败: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将处理结果写入MySQL数据库")
    parser.add_argument("--pickle",          required=True, help="pickle 文件路径")
    parser.add_argument("--video",           default="",    help="原始视频文件路径")
    parser.add_argument("--camera_id",       type=int, default=1, help="摄像头ID（默认1）")
    parser.add_argument("--camera_location", default="未知位置",   help="摄像头位置描述")
    args = parser.parse_args()

    ingest(
        pickle_path=args.pickle,
        video_path=args.video,
        camera_id=args.camera_id,
        camera_location=args.camera_location,
    )
