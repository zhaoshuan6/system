#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
搜索路由
  POST /api/search/text        - 文字搜图
  POST /api/search/image       - 以图搜图
  POST /api/search/trajectory  - 人物轨迹追踪
"""

import uuid
import logging
from pathlib import Path

import numpy as np
import torch
from flask import Blueprint, request, jsonify
from PIL import Image

logger = logging.getLogger(__name__)
search_bp = Blueprint("search", __name__)

QUERY_DIR = Path("data/uploads/queries")
QUERY_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ----------------------------------------------------------------
#  模型单例
# ----------------------------------------------------------------
_clip_model = None
_clip_preprocess = None
_device = None

def get_clip():
    global _clip_model, _clip_preprocess, _device
    if _clip_model is None:
        import clip
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _clip_model, _clip_preprocess = clip.load("ViT-B/32", device=_device)
        _clip_model.eval()
        logger.info(f"✅ CLIP 加载完成，设备: {_device}")
    return _clip_model, _clip_preprocess, _device


_feature_index = None

def get_index():
    global _feature_index
    if _feature_index is None:
        from backend.models.feature_index import FeatureIndex
        from backend.database.db import get_session
        from config import FAISS_CONFIG
        _feature_index = FeatureIndex(
            dim=FAISS_CONFIG["dim"],
            index_path=FAISS_CONFIG["index_path"],
        )
        if not _feature_index.load():
            session = get_session()
            try:
                _feature_index.build_from_db(session)
                _feature_index.save()
            finally:
                session.close()
    return _feature_index


# ----------------------------------------------------------------
#  工具函数
# ----------------------------------------------------------------

def extract_text_feature(text: str) -> np.ndarray:
    import clip
    model, _, device = get_clip()
    tokens = clip.tokenize([text]).to(device)
    with torch.no_grad():
        feat = model.encode_text(tokens)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]


def extract_image_feature(image: Image.Image) -> np.ndarray:
    model, preprocess, device = get_clip()
    tensor = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]


def format_results(raw_results: list) -> list:
    formatted = []
    for r in raw_results:
        appearances = []
        for a in r.get("appearances", []):
            appearances.append({
                "frame_time":  round(a["frame_time"], 2),
                "frame_path":  a["frame_path"],
                "bbox":        a["bbox"],
                "score":       round(a["score"], 4),
            })
        appearances.sort(key=lambda x: x["frame_time"])
        formatted.append({
            "video_id":        r["video_id"],
            "file_path":       r["file_path"],
            "camera_location": r.get("camera_location", "未知位置"),
            "max_score":       round(r["max_score"], 4),
            "appearances":     appearances,
        })
    return formatted


def _crop_main_person(image: Image.Image) -> Image.Image:
    try:
        import cv2
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        results = model(img_bgr, classes=[0], verbose=False)
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return image
        best = max(boxes, key=lambda b: float(b.conf[0]))
        x1, y1, x2, y2 = map(int, best.xyxy[0].tolist())
        h, w = img_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return image.crop((x1, y1, x2, y2))
    except Exception as e:
        logger.warning(f"人物裁剪失败，使用原图: {e}")
        return image


# ----------------------------------------------------------------
#  POST /api/search/text
# ----------------------------------------------------------------

@search_bp.route("/text", methods=["POST"])
def search_by_text():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "请输入搜索描述"}), 400

    top_k = int(data.get("top_k", 10))
    try:
        feat = extract_text_feature(query)
        index = get_index()
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400
        raw = index.search_and_group_by_video(feat, top_k=top_k * 5)
        results = format_results(raw[:top_k])
        return jsonify({"success": True, "query": query, "count": len(results), "results": results})
    except Exception as e:
        logger.error(f"文字搜图失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/search/image
# ----------------------------------------------------------------

@search_bp.route("/image", methods=["POST"])
def search_by_image():
    if "image" not in request.files:
        return jsonify({"success": False, "error": "请上传图片文件"}), 400

    file = request.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        return jsonify({"success": False, "error": f"不支持的图片格式: {suffix}"}), 400

    top_k = int(request.form.get("top_k", 10))
    save_path = QUERY_DIR / f"{uuid.uuid4().hex}{suffix}"
    file.save(str(save_path))

    try:
        image = Image.open(save_path).convert("RGB")
        person_image = _crop_main_person(image)
        feat = extract_image_feature(person_image)
        index = get_index()
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400
        raw = index.search_and_group_by_video(feat, top_k=top_k * 5)
        results = format_results(raw[:top_k])
        return jsonify({
            "success": True,
            "count": len(results),
            "results": results,
            "detected_person": person_image.size != image.size,
        })
    except Exception as e:
        logger.error(f"以图搜图失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/search/trajectory  人物轨迹追踪
# ----------------------------------------------------------------

@search_bp.route("/trajectory", methods=["POST"])
def search_trajectory():
    """
    上传人物图片，返回该人物在所有摄像头的完整时间线轨迹。
    threshold: 相似度阈值（默认0.20，越高越严格）
    top_k:     最多检索多少条原始结果（默认100）
    """
    if "image" not in request.files:
        return jsonify({"success": False, "error": "请上传人物图片"}), 400

    file = request.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        return jsonify({"success": False, "error": f"不支持的图片格式: {suffix}"}), 400

    threshold = float(request.form.get("threshold", 0.20))
    top_k     = int(request.form.get("top_k", 100))

    save_path = QUERY_DIR / f"traj_{uuid.uuid4().hex}{suffix}"
    file.save(str(save_path))

    try:
        image = Image.open(save_path).convert("RGB")
        person_image = _crop_main_person(image)
        feat = extract_image_feature(person_image)

        index = get_index()
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400

        # 检索所有匹配结果
        raw_hits = index.search(feat, top_k=top_k)

        # 过滤低分
        hits = [h for h in raw_hits if h["score"] >= threshold]

        if not hits:
            return jsonify({
                "success": True,
                "total_appearances": 0,
                "trajectory": [],
                "location_nodes": [],
                "message": f"未找到相似度 ≥ {threshold} 的结果，请尝试降低阈值或换一张更清晰的图片",
            })

        # 同帧去重（保留最高分）
        seen_frames = {}
        for h in hits:
            fid = h["frame_id"]
            if fid not in seen_frames or h["score"] > seen_frames[fid]["score"]:
                seen_frames[fid] = h
        hits = list(seen_frames.values())

        # 按 (video_id, frame_time) 排序
        hits.sort(key=lambda x: (x["video_id"], x["frame_time"]))

        # 构建逐帧轨迹
        trajectory = []
        for i, h in enumerate(hits):
            trajectory.append({
                "step":            i + 1,
                "video_id":        h["video_id"],
                "camera_location": h["camera_location"],
                "frame_time":      round(h["frame_time"], 2),
                "frame_path":      h["frame_path"],
                "score":           round(h["score"], 4),
                "bbox":            {"x": h["bbox_x"], "y": h["bbox_y"],
                                    "w": h["bbox_w"], "h": h["bbox_h"]},
            })

        # 合并连续同摄像头为位置节点（用于轨迹图动画）
        location_nodes = []
        for t in trajectory:
            if (not location_nodes or
                    location_nodes[-1]["camera_location"] != t["camera_location"]):
                location_nodes.append({
                    "step":            len(location_nodes) + 1,
                    "camera_location": t["camera_location"],
                    "video_id":        t["video_id"],
                    "first_seen":      t["frame_time"],
                    "last_seen":       t["frame_time"],
                    "frame_path":      t["frame_path"],
                    "score":           t["score"],
                    "appearances":     1,
                })
            else:
                node = location_nodes[-1]
                node["last_seen"]   = t["frame_time"]
                node["appearances"] += 1
                if t["score"] > node["score"]:
                    node["score"]      = t["score"]
                    node["frame_path"] = t["frame_path"]

        return jsonify({
            "success":           True,
            "total_appearances": len(trajectory),
            "location_count":    len(location_nodes),
            "trajectory":        trajectory,
            "location_nodes":    location_nodes,
        })

    except Exception as e:
        logger.error(f"轨迹追踪失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
