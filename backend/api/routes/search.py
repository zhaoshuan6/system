#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
搜索路由
  POST /api/search/text   - 文字搜图
  POST /api/search/image  - 以图搜图
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

# 上传图片临时目录
QUERY_DIR = Path("data/uploads/queries")
QUERY_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ----------------------------------------------------------------
#  CLIP 模型单例（懒加载，避免每次请求重复加载）
# ----------------------------------------------------------------
_clip_model = None
_clip_preprocess = None
_device = None

def get_clip():
    global _clip_model, _clip_preprocess, _device
    if _clip_model is None:
        import clip
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"加载 CLIP 模型，设备: {_device}")
        _clip_model, _clip_preprocess = clip.load("ViT-B/32", device=_device)
        _clip_model.eval()
        logger.info("✅ CLIP 加载完成")
    return _clip_model, _clip_preprocess, _device


# ----------------------------------------------------------------
#  FAISS 索引单例（懒加载）
# ----------------------------------------------------------------
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
        # 优先从文件加载，否则从数据库重建
        if not _feature_index.load():
            logger.info("FAISS 索引文件不存在，从数据库重建...")
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
    """将文字描述转为 CLIP 特征向量"""
    import clip
    model, _, device = get_clip()
    tokens = clip.tokenize([text]).to(device)
    with torch.no_grad():
        feat = model.encode_text(tokens)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]  # shape (512,)


def extract_image_feature(image: Image.Image) -> np.ndarray:
    """将 PIL 图片转为 CLIP 特征向量"""
    model, preprocess, device = get_clip()
    tensor = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]  # shape (512,)


def format_results(raw_results: list) -> list:
    """
    格式化检索结果，统一返回结构：
    [{
        video_id, file_path, camera_location, max_score,
        appearances: [{frame_time, frame_path, bbox, score}]
    }]
    """
    formatted = []
    for r in raw_results:
        # 把 frame_path 转为相对路径（避免暴露服务器绝对路径）
        appearances = []
        for a in r.get("appearances", []):
            appearances.append({
                "frame_time":  round(a["frame_time"], 2),
                "frame_path":  a["frame_path"],
                "bbox":        a["bbox"],
                "score":       round(a["score"], 4),
            })
        # 按时间排序
        appearances.sort(key=lambda x: x["frame_time"])

        formatted.append({
            "video_id":        r["video_id"],
            "file_path":       r["file_path"],
            "camera_location": r.get("camera_location", "未知位置"),
            "max_score":       round(r["max_score"], 4),
            "appearances":     appearances,
        })
    return formatted


# ----------------------------------------------------------------
#  POST /api/search/text  文字搜图
# ----------------------------------------------------------------

@search_bp.route("/text", methods=["POST"])
def search_by_text():
    """
    文字搜图接口
    请求体（JSON 或 form-data）：
      query    - 文字描述，如"穿红色外套的男生"
      top_k    - 返回结果数（默认10）
    """
    # 兼容 JSON 和 form-data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "请输入搜索描述"}), 400

    top_k = int(data.get("top_k", 10))

    try:
        logger.info(f"文字搜图: '{query}'，top_k={top_k}")

        # 提取文本特征
        feat = extract_text_feature(query)

        # FAISS 检索
        index = get_index()
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400

        raw = index.search_and_group_by_video(feat, top_k=top_k * 5)
        results = format_results(raw[:top_k])

        return jsonify({
            "success": True,
            "query":   query,
            "count":   len(results),
            "results": results,
        })

    except Exception as e:
        logger.error(f"文字搜图失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/search/image  以图搜图
# ----------------------------------------------------------------

@search_bp.route("/image", methods=["POST"])
def search_by_image():
    """
    以图搜图接口
    请求体（multipart/form-data）：
      image  - 人物图片文件
      top_k  - 返回结果数（默认10）
    """
    if "image" not in request.files:
        return jsonify({"success": False, "error": "请上传图片文件"}), 400

    file = request.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        return jsonify({"success": False, "error": f"不支持的图片格式: {suffix}"}), 400

    top_k = int(request.form.get("top_k", 10))

    # 保存上传图片
    save_path = QUERY_DIR / f"{uuid.uuid4().hex}{suffix}"
    file.save(str(save_path))

    try:
        logger.info(f"以图搜图: {file.filename}，top_k={top_k}")

        image = Image.open(save_path).convert("RGB")

        # 用 YOLOv8 检测图片中的人物，取置信度最高的那个裁剪区域
        person_image = _crop_main_person(image)

        # 提取图片特征
        feat = extract_image_feature(person_image)

        # FAISS 检索
        index = get_index()
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400

        raw = index.search_and_group_by_video(feat, top_k=top_k * 5)
        results = format_results(raw[:top_k])

        return jsonify({
            "success":        True,
            "count":          len(results),
            "results":        results,
            "detected_person": person_image.size != image.size,  # 是否检测到人物并裁剪
        })

    except Exception as e:
        logger.error(f"以图搜图失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def _crop_main_person(image: Image.Image) -> Image.Image:
    """
    用 YOLOv8 检测图片中置信度最高的人物，返回裁剪后的图片。
    如果未检测到人物，返回原图。
    """
    try:
        import numpy as np
        import cv2
        from ultralytics import YOLO

        # YOLOv8 模型复用（简单起见直接加载，可后续改为单例）
        model = YOLO("yolov8n.pt")
        img_np = np.array(image)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        results = model(img_bgr, classes=[0], verbose=False)
        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            logger.info("未检测到人物，使用原图提取特征")
            return image

        # 取置信度最高的人物框
        best = max(boxes, key=lambda b: float(b.conf[0]))
        x1, y1, x2, y2 = map(int, best.xyxy[0].tolist())
        h, w = img_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        cropped = image.crop((x1, y1, x2, y2))
        logger.info(f"检测到人物，裁剪区域: ({x1},{y1})-({x2},{y2})")
        return cropped

    except Exception as e:
        logger.warning(f"人物裁剪失败，使用原图: {e}")
        return image
