#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ReID 特征索引 —— 使用 OSNet-x1.0 提取行人重识别特征
用于以图搜图和轨迹追踪，比 CLIP 对同一人物在不同摄像头/角度下的匹配更准确。

依赖：pip install torchreid
"""

import sys
import pickle
import logging
from pathlib import Path

import faiss
import numpy as np
import torch

logger = logging.getLogger(__name__)

_reid_extractor = None


def _get_extractor(device: str = None):
    global _reid_extractor
    if _reid_extractor is None:
        import torchreid
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        _reid_extractor = torchreid.utils.FeatureExtractor(
            model_name="osnet_x1_0",
            device=device,
        )
        logger.info(f"✅ OSNet-x1.0 ReID 模型加载完成，设备: {device}")
    return _reid_extractor


def extract_reid_feature(image) -> np.ndarray:
    """
    从 PIL Image 提取 ReID 特征 (512维, L2归一化)。
    """
    extractor = _get_extractor()
    arr = np.array(image)  # PIL → numpy HWC uint8 RGB
    result = extractor([arr])
    feat = result[0].cpu().numpy() if isinstance(result, torch.Tensor) else np.array(result[0])
    feat = feat / (np.linalg.norm(feat) + 1e-8)
    return feat


class ReidIndex:
    """
    ReID 专用 FAISS 索引。
    接口与 FeatureIndex 完全一致，可透明替换。
    """

    def __init__(self, dim: int = 512, index_path: str = "data/database/reid.index"):
        self.dim = dim
        self.index_path = Path(index_path)
        self.meta_path = self.index_path.with_suffix(".meta.pkl")
        self._index = faiss.IndexFlatIP(dim)
        self._meta: list = []
        self._gpu_vectors: torch.Tensor | None = None  # (N, dim) on CUDA

    def _sync_gpu(self):
        if not torch.cuda.is_available() or self._index.ntotal == 0:
            self._gpu_vectors = None
            return
        ptr = faiss.rev_swig_ptr(self._index.get_xb(), self._index.ntotal * self.dim)
        arr = np.array(ptr, dtype=np.float32).reshape(self._index.ntotal, self.dim).copy()
        self._gpu_vectors = torch.from_numpy(arr).cuda()
        logger.info(f"ReID 向量已上传 GPU，shape={tuple(self._gpu_vectors.shape)}")

    # ----------------------------------------------------------------
    #  构建索引（从数据库读帧图片 + bbox，提取 OSNet 特征）
    # ----------------------------------------------------------------

    def build_from_db(self, session) -> int:
        from PIL import Image
        from backend.database.models import DetectedObject, KeyFrame, VideoMetadata, Trajectory

        logger.info("构建 ReID 索引：从数据库读取帧图片 → OSNet 提取特征...")

        rows = (
            session.query(DetectedObject, KeyFrame, VideoMetadata)
            .join(KeyFrame,      DetectedObject.frame_id == KeyFrame.frame_id)
            .join(VideoMetadata, KeyFrame.video_id == VideoMetadata.video_id)
            .all()
        )
        if not rows:
            logger.warning("数据库无检测目标，ReID 索引为空")
            return 0

        traj_map = {}
        for t in session.query(Trajectory).all():
            traj_map.setdefault(t.video_id, t.camera_location or "未知位置")

        project_root = Path(sys.path[0]) if sys.path else Path.cwd()
        extractor    = _get_extractor()

        features, meta, skipped = [], [], 0
        batch_crops, batch_meta = [], []

        def _flush_batch():
            if not batch_crops:
                return
            try:
                arrays = [np.array(c) for c in batch_crops]  # PIL → numpy HWC uint8
                result = extractor(arrays)
                feats = result.cpu().numpy() if isinstance(result, torch.Tensor) else np.array(result)
                for feat, m in zip(feats, batch_meta):
                    feat = feat / (np.linalg.norm(feat) + 1e-8)
                    features.append(feat)
                    meta.append(m)
            except Exception as e:
                logger.warning(f"批量 ReID 提取失败: {e}")
            batch_crops.clear()
            batch_meta.clear()

        total = len(rows)
        for i, (obj, kf, video) in enumerate(rows):
            if i % 100 == 0:
                logger.info(f"  ReID 特征提取进度: {i}/{total}")

            # 解析帧路径
            fp = Path(kf.frame_path)
            if not fp.is_absolute():
                fp = (project_root / fp).resolve()
            if not fp.exists():
                fname = Path(kf.frame_path).name
                candidates = list((project_root / "data" / "processed").rglob(fname))
                fp = candidates[0] if candidates else None
            if fp is None or not fp.exists():
                skipped += 1
                continue

            try:
                img   = Image.open(fp).convert("RGB")
                iw, ih = img.size
                x1 = max(0,  obj.bbox_x)
                y1 = max(0,  obj.bbox_y)
                x2 = min(iw, obj.bbox_x + obj.bbox_w)
                y2 = min(ih, obj.bbox_y + obj.bbox_h)
                if x2 <= x1 or y2 <= y1:
                    skipped += 1
                    continue
                crop = img.crop((x1, y1, x2, y2))
            except Exception as e:
                logger.warning(f"图片读取失败 object_id={obj.object_id}: {e}")
                skipped += 1
                continue

            batch_crops.append(crop)
            batch_meta.append({
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

            if len(batch_crops) >= 32:
                _flush_batch()

        _flush_batch()

        if not features:
            logger.warning("无有效特征，ReID 索引为空")
            return 0

        features_np = np.array(features, dtype=np.float32)
        self._index = faiss.IndexFlatIP(self.dim)
        self._index.add(features_np)
        self._meta = meta
        self._sync_gpu()

        if skipped:
            logger.warning(f"跳过 {skipped} 条（图片缺失或裁剪无效）")
        logger.info(f"✅ ReID 索引构建完成，共 {len(meta)} 条向量")
        return len(meta)

    # ----------------------------------------------------------------
    #  检索
    # ----------------------------------------------------------------

    def search(self, query_feature: np.ndarray, top_k: int = 20) -> list:
        if self._index.ntotal == 0:
            return []
        query = query_feature.astype(np.float32).reshape(1, -1)
        query /= (np.linalg.norm(query) + 1e-8)
        k = min(top_k, self._index.ntotal)

        GPU_THRESHOLD = 10000  # 向量数低于此值 CPU 更快
        if self._gpu_vectors is not None and self._index.ntotal >= GPU_THRESHOLD:
            q = torch.from_numpy(query).cuda()
            scores_t = torch.mm(q, self._gpu_vectors.T)[0]
            top_scores, top_idx = torch.topk(scores_t, k)
            scores_arr  = top_scores.cpu().numpy()
            indices_arr = top_idx.cpu().numpy()
        else:
            scores_2d, indices_2d = self._index.search(query, k)
            scores_arr  = scores_2d[0]
            indices_arr = indices_2d[0]

        results = []
        for score, idx in zip(scores_arr, indices_arr):
            if idx < 0:
                continue
            item = dict(self._meta[int(idx)])
            item["score"] = float(score)
            results.append(item)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def search_and_group_by_video(self, query_feature: np.ndarray, top_k: int = 50) -> list:
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
                "bbox":       {"x": r["bbox_x"], "y": r["bbox_y"],
                               "w": r["bbox_w"], "h": r["bbox_h"]},
                "score":      r["score"],
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
        logger.info(f"✅ ReID 索引已保存: {self.index_path}")

    def load(self) -> bool:
        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        self._index = faiss.read_index(str(self.index_path))
        with open(self.meta_path, "rb") as f:
            self._meta = pickle.load(f)
        self._sync_gpu()
        logger.info(f"✅ ReID 索引已加载，共 {self._index.ntotal} 条向量")
        return True

    @property
    def total(self) -> int:
        return self._index.ntotal
