#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FAISS 特征索引管理模块
- 从数据库加载所有人物的 CLIP 特征，构建 FAISS 索引
- 支持文字搜图（文本特征查询）和以图搜图（图片特征查询）
- 索引持久化保存/加载
"""

import logging
import pickle
from pathlib import Path

import faiss
import numpy as np

logger = logging.getLogger(__name__)


class FeatureIndex:
    """
    FAISS 特征索引管理器

    使用内积索引（IndexFlatIP）+ L2 归一化特征 = 余弦相似度检索
    """

    def __init__(self, dim: int = 512, index_path: str = "data/database/faiss.index"):
        self.dim = dim
        self.index_path = Path(index_path)
        self.meta_path = self.index_path.with_suffix(".meta.pkl")

        self._index = faiss.IndexFlatIP(dim)

        # 元数据列表，与 FAISS 向量一一对应
        # 每条: {object_id, frame_id, video_id, frame_time, frame_path,
        #        bbox_x, bbox_y, bbox_w, bbox_h, confidence, camera_location}
        self._meta: list = []

    # ----------------------------------------------------------------
    #  构建索引
    # ----------------------------------------------------------------

    def build_from_db(self, session) -> int:
        """
        从数据库读取所有 DetectedObject 的特征向量，构建 FAISS 索引

        Returns:
            索引中的向量数量
        """
        from backend.database.models import DetectedObject, KeyFrame, VideoMetadata, Trajectory

        logger.info("从数据库构建 FAISS 索引...")

        rows = (
            session.query(DetectedObject, KeyFrame, VideoMetadata)
            .join(KeyFrame, DetectedObject.frame_id == KeyFrame.frame_id)
            .join(VideoMetadata, KeyFrame.video_id == VideoMetadata.video_id)
            .all()
        )

        if not rows:
            logger.warning("数据库中没有检测目标数据，索引为空")
            return 0

        # 查询轨迹表获取摄像头位置（video_id → camera_location）
        traj_map = {}
        trajs = session.query(Trajectory).all()
        for t in trajs:
            if t.video_id not in traj_map:
                traj_map[t.video_id] = t.camera_location or "未知位置"

        features = []
        meta = []

        for obj, kf, video in rows:
            feat = obj.get_feature()
            features.append(feat)
            meta.append({
                "object_id":       obj.object_id,
                "frame_id":        obj.frame_id,
                "video_id":        video.video_id,
                "file_path":       video.file_path,
                "frame_time":      kf.frame_time,
                "frame_path":      kf.frame_path,
                "bbox_x":          obj.bbox_x,
                "bbox_y":          obj.bbox_y,
                "bbox_w":          obj.bbox_w,
                "bbox_h":          obj.bbox_h,
                "confidence":      obj.confidence,
                "camera_location": traj_map.get(video.video_id, "未知位置"),
            })

        features_np = np.array(features, dtype=np.float32)

        self._index = faiss.IndexFlatIP(self.dim)
        self._index.add(features_np)
        self._meta = meta

        logger.info(f"✅ FAISS 索引构建完成，共 {len(meta)} 条向量")
        return len(meta)

    # ----------------------------------------------------------------
    #  检索
    # ----------------------------------------------------------------

    def search(self, query_feature: np.ndarray, top_k: int = 20) -> list:
        """
        检索最相似的 Top-K 结果（逐条返回）
        """
        if self._index.ntotal == 0:
            return []

        query = query_feature.astype(np.float32).reshape(1, -1)
        query /= (np.linalg.norm(query) + 1e-8)

        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            item = dict(self._meta[idx])
            item["score"] = float(score)
            results.append(item)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def search_and_group_by_video(self, query_feature: np.ndarray, top_k: int = 50) -> list:
        """
        检索后按视频分组，返回结构：
        [{video_id, file_path, camera_location, max_score,
          appearances: [{frame_time, frame_path, bbox, score}]}]
        """
        raw = self.search(query_feature, top_k=top_k)

        video_map = {}
        for r in raw:
            vid = r["video_id"]
            if vid not in video_map:
                video_map[vid] = {
                    "video_id":        vid,
                    "file_path":       r["file_path"],
                    "camera_location": r["camera_location"],
                    "max_score":       r["score"],
                    "appearances":     [],
                }
            video_map[vid]["appearances"].append({
                "frame_time": r["frame_time"],
                "frame_path": r["frame_path"],
                "bbox": {"x": r["bbox_x"], "y": r["bbox_y"],
                         "w": r["bbox_w"], "h": r["bbox_h"]},
                "score": r["score"],
            })
            video_map[vid]["max_score"] = max(video_map[vid]["max_score"], r["score"])

        return sorted(video_map.values(), key=lambda x: x["max_score"], reverse=True)

    # ----------------------------------------------------------------
    #  持久化
    # ----------------------------------------------------------------

    def save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self.index_path))
        with open(self.meta_path, "wb") as f:
            pickle.dump(self._meta, f)
        logger.info(f"✅ FAISS 索引已保存: {self.index_path}")

    def load(self) -> bool:
        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        self._index = faiss.read_index(str(self.index_path))
        with open(self.meta_path, "rb") as f:
            self._meta = pickle.load(f)
        logger.info(f"✅ FAISS 索引已加载，共 {self._index.ntotal} 条向量")
        return True

    @property
    def total(self) -> int:
        return self._index.ntotal
