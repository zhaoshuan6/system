#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
搜索路由
  POST /api/search/detect      - 检测图片中所有人物，返回边界框列表
  POST /api/search/text        - 文字搜图
  POST /api/search/image       - 以图搜图
  POST /api/search/trajectory  - 人物轨迹追踪
"""

import uuid
import logging
from pathlib import Path

import numpy as np
import torch
from flask import Blueprint, request, jsonify, g
from PIL import Image
from backend.api.routes.auth import login_required

logger = logging.getLogger(__name__)
search_bp = Blueprint("search", __name__)


def _save_history(search_type: str, result_count: int,
                  query_text: str = None, query_image: str = None):
    """搜索成功后记录历史，失败不影响主流程。"""
    try:
        from backend.database.db import get_session
        from backend.database.models import SearchHistory
        session = get_session()
        try:
            record = SearchHistory(
                user_id      = g.current_user["user_id"],
                username     = g.current_user["username"],
                search_type  = search_type,
                query_text   = query_text,
                query_image  = query_image,
                result_count = result_count,
            )
            session.add(record)
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"记录搜索历史失败（不影响搜索结果）: {e}")

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


_yolo_model = None

def get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8x.pt")
        logger.info("✅ YOLOv8x 加载完成")
    return _yolo_model


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


_reid_index = None
_REID_UNAVAILABLE = object()   # sentinel: torchreid not installed, stop retrying

def get_reid_index():
    """加载 ReID（OSNet）索引，失败时返回 None（调用方降级到 CLIP）。"""
    global _reid_index
    if _reid_index is _REID_UNAVAILABLE:
        return None
    if _reid_index is None:
        try:
            import importlib.util
            if importlib.util.find_spec("torchreid") is None:
                raise ImportError("torchreid 未安装，以图搜图将使用 CLIP 降级")
            from backend.models.reid_index import ReidIndex
            from backend.database.db import get_session
            from config import REID_CONFIG
            idx = ReidIndex(
                dim=REID_CONFIG["dim"],
                index_path=REID_CONFIG["index_path"],
            )
            if not idx.load():
                logger.info("ReID 索引文件不存在，从数据库构建（首次较慢）...")
                session = get_session()
                try:
                    idx.build_from_db(session)
                    if idx.total > 0:
                        idx.save()
                finally:
                    session.close()
            _reid_index = idx
        except ImportError as e:
            logger.warning(f"ReID 不可用（以图搜图将使用 CLIP）: {e}")
            _reid_index = _REID_UNAVAILABLE
        except Exception as e:
            logger.warning(f"ReID 索引加载失败，以图搜图将使用 CLIP: {e}")
            _reid_index = _REID_UNAVAILABLE
    return _reid_index if _reid_index is not _REID_UNAVAILABLE else None


def _image_feature_and_index(person_image):
    """
    为以图搜图/轨迹追踪返回 (特征向量, 索引)。
    优先使用 ReID（OSNet），不可用时降级到 CLIP。
    """
    reid = get_reid_index()
    if reid is not None and reid.total > 0:
        from backend.models.reid_index import extract_reid_feature
        return extract_reid_feature(person_image), reid
    feat = extract_image_feature(person_image)
    return feat, get_index()


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
    """自动选取置信度最高的人物框裁剪（兜底逻辑）。"""
    try:
        import cv2
        model = get_yolo()
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


def _crop_by_bbox(image: Image.Image, bbox: list) -> Image.Image:
    """按用户指定的边界框裁剪。"""
    x1, y1, x2, y2 = bbox
    img_w, img_h = image.size
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(img_w, int(x2)), min(img_h, int(y2))
    return image.crop((x1, y1, x2, y2))


def _resolve_person_image(req):
    """
    从请求中解析出 (save_path, person_image)：
    - 若携带 image_key + bbox：使用服务端已保存图片按指定框裁剪
    - 若携带 image 文件：保存后自动裁剪置信度最高的人物（兜底）
    """
    image_key = req.form.get("image_key", "").strip()
    bbox_str  = req.form.get("bbox", "").strip()

    if image_key and bbox_str:
        save_path = QUERY_DIR / image_key
        if not save_path.exists():
            raise FileNotFoundError("图片已过期，请重新上传")
        image = Image.open(save_path).convert("RGB")
        bbox  = list(map(int, bbox_str.split(",")))
        return save_path, _crop_by_bbox(image, bbox)

    if "image" not in req.files:
        raise ValueError("请上传图片文件或提供 image_key")

    file   = req.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        raise ValueError(f"不支持的图片格式: {suffix}")
    save_path = QUERY_DIR / f"{uuid.uuid4().hex}{suffix}"
    file.save(str(save_path))
    image = Image.open(save_path).convert("RGB")
    return save_path, _crop_main_person(image)


# ----------------------------------------------------------------
#  POST /api/search/detect  检测所有人物，返回边界框
# ----------------------------------------------------------------

@search_bp.route("/detect", methods=["POST"])
@login_required
def detect_persons():
    if "image" not in request.files:
        return jsonify({"success": False, "error": "请上传图片文件"}), 400

    file   = request.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        return jsonify({"success": False, "error": f"不支持的图片格式: {suffix}"}), 400

    image_key = uuid.uuid4().hex
    save_path = QUERY_DIR / f"{image_key}{suffix}"
    file.save(str(save_path))

    try:
        import cv2
        image   = Image.open(save_path).convert("RGB")
        img_w, img_h = image.size
        model   = get_yolo()
        img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        results = model(img_bgr, classes=[0], verbose=False)
        boxes   = results[0].boxes

        persons = []
        if boxes is not None:
            for box in boxes:
                conf = float(box.conf[0])
                if conf < 0.3:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_w, x2), min(img_h, y2)
                if (x2 - x1) < 10 or (y2 - y1) < 10:
                    continue
                persons.append({
                    "bbox":       [x1, y1, x2, y2],
                    "confidence": round(conf, 3),
                })

        persons.sort(key=lambda p: p["confidence"], reverse=True)

        return jsonify({
            "success":    True,
            "image_key":  f"{image_key}{suffix}",
            "image_size": [img_w, img_h],
            "persons":    persons,
        })
    except Exception as e:
        logger.error(f"人物检测失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/search/text
# ----------------------------------------------------------------

@search_bp.route("/text", methods=["POST"])
@login_required
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
        _save_history("text", len(results), query_text=query)
        return jsonify({"success": True, "query": query, "count": len(results), "results": results})
    except Exception as e:
        logger.error(f"文字搜图失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/search/image
# ----------------------------------------------------------------

@search_bp.route("/image", methods=["POST"])
@login_required
def search_by_image():
    top_k = int(request.form.get("top_k", 10))

    try:
        save_path, person_image = _resolve_person_image(request)
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        feat, index = _image_feature_and_index(person_image)
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400
        raw     = index.search_and_group_by_video(feat, top_k=top_k * 5)
        results = format_results(raw[:top_k])
        _save_history("image", len(results), query_image=str(save_path))
        return jsonify({
            "success": True,
            "count":   len(results),
            "results": results,
        })
    except Exception as e:
        logger.error(f"以图搜图失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/search/trajectory  人物轨迹追踪
# ----------------------------------------------------------------

@search_bp.route("/trajectory", methods=["POST"])
@login_required
def search_trajectory():
    threshold = float(request.form.get("threshold", 0.20))
    top_k     = int(request.form.get("top_k", 100))

    try:
        save_path, person_image = _resolve_person_image(request)
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        feat, index = _image_feature_and_index(person_image)
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400

        raw_hits = index.search(feat, top_k=top_k)
        hits = [h for h in raw_hits if h["score"] >= threshold]

        if not hits:
            return jsonify({
                "success": True,
                "total_appearances": 0,
                "trajectory": [],
                "location_nodes": [],
                "message": f"未找到相似度 ≥ {threshold} 的结果，请尝试降低阈值或换一张更清晰的图片",
            })

        seen_frames = {}
        for h in hits:
            fid = h["frame_id"]
            if fid not in seen_frames or h["score"] > seen_frames[fid]["score"]:
                seen_frames[fid] = h
        hits = list(seen_frames.values())

        hits.sort(key=lambda x: (x["video_id"], x["frame_time"]))

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

        _save_history("trajectory", len(location_nodes), query_image=str(save_path))
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


# ----------------------------------------------------------------
#  POST /api/search/from_frame  用已有帧图片的 bbox 区域搜索
# ----------------------------------------------------------------

def _resolve_frame_path(raw_path: str):
    """解析帧路径，支持绝对路径和相对路径，找不到时在 data/processed 中兜底搜索。"""
    import sys as _sys
    fp = Path(raw_path)
    # 相对路径：拼接项目根目录（与 get_frame 保持一致）
    if not fp.is_absolute():
        project_root = Path(_sys.path[0]) if _sys.path else Path.cwd()
        fp = (project_root / fp).resolve()
    else:
        fp = fp.resolve()
    if fp.exists():
        return fp
    # 兜底：在 data/processed 中按文件名查找
    fname = Path(raw_path).name
    project_root = Path(_sys.path[0]) if _sys.path else Path.cwd()
    candidates = list((project_root / "data" / "processed").rglob(fname))
    if candidates:
        return candidates[0]
    return None


@search_bp.route("/from_frame", methods=["POST"])
@login_required
def search_from_frame():
    """
    使用数据库中已有帧图片的指定区域进行搜索。
      frame_path:  帧文件路径（服务端路径）
      bbox:        "x,y,w,h"（像素坐标，与 appearance.bbox 对应）
      search_type: "image" 或 "trajectory"
      top_k:       返回数量（图片搜索用）
      threshold:   相似度阈值（轨迹追踪用）
    """
    frame_path  = request.form.get("frame_path", "").strip()
    bbox_str    = request.form.get("bbox", "").strip()
    search_type = request.form.get("search_type", "image")
    top_k       = int(request.form.get("top_k", 10))
    threshold   = float(request.form.get("threshold", 0.20))

    if not frame_path or not bbox_str:
        return jsonify({"success": False, "error": "缺少 frame_path 或 bbox 参数"}), 400

    fp = _resolve_frame_path(frame_path)
    if fp is None:
        return jsonify({"success": False, "error": f"帧图片不存在: {frame_path}"}), 404

    try:
        image = Image.open(fp).convert("RGB")
        x, y, w, h = map(int, bbox_str.split(","))
        img_w, img_h = image.size
        x1, y1 = max(0, x),     max(0, y)
        x2, y2 = min(img_w, x + w), min(img_h, y + h)
        person_image = image.crop((x1, y1, x2, y2))

        feat, index = _image_feature_and_index(person_image)
        if index.total == 0:
            return jsonify({"success": False, "error": "索引为空，请先上传并处理视频"}), 400

        if search_type == "trajectory":
            raw_hits = index.search(feat, top_k=100)
            hits = [h for h in raw_hits if h["score"] >= threshold]
            if not hits:
                return jsonify({
                    "success": True,
                    "total_appearances": 0,
                    "trajectory": [],
                    "location_nodes": [],
                    "message": f"未找到相似度 ≥ {threshold} 的结果，请尝试降低阈值",
                })

            seen_frames = {}
            for h in hits:
                fid = h["frame_id"]
                if fid not in seen_frames or h["score"] > seen_frames[fid]["score"]:
                    seen_frames[fid] = h
            hits = list(seen_frames.values())
            hits.sort(key=lambda x: (x["video_id"], x["frame_time"]))

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

        else:  # image search
            raw     = index.search_and_group_by_video(feat, top_k=top_k * 5)
            results = format_results(raw[:top_k])
            return jsonify({
                "success": True,
                "count":   len(results),
                "results": results,
            })

    except Exception as e:
        logger.error(f"从帧搜索失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
