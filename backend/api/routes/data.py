#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据管理路由
  POST   /api/data/upload          - 上传并处理视频
  GET    /api/data/videos          - 获取所有视频列表
  GET    /api/data/videos/<id>     - 获取单个视频详情
  GET    /api/data/frame           - 获取关键帧图片（兼容Windows绝对路径）
  GET    /api/data/video_file/<id> - 视频文件流（支持Range，前端可拖进度条）
  POST   /api/data/rebuild_index   - 重建 FAISS 索引
  DELETE /api/data/videos/<id>     - 删除视频及相关数据
"""

import re
import uuid
import logging
from pathlib import Path

from flask import Blueprint, request, jsonify, send_file, Response

logger = logging.getLogger(__name__)
data_bp = Blueprint("data", __name__)

UPLOAD_DIR = Path("data/uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv"}


# ----------------------------------------------------------------
#  GET /api/data/frame  获取关键帧图片
# ----------------------------------------------------------------

@data_bp.route("/frame", methods=["GET"])
def get_frame():
    """
    获取关键帧图片。
    数据库中存的是 Windows 绝对路径（如 C:\\vedio_retrieval_system\\...）
    直接用 Path() 解析，Windows / Linux 均兼容。
    """
    frame_path = request.args.get("path", "").strip()
    if not frame_path:
        return jsonify({"error": "缺少 path 参数"}), 400

    path = Path(frame_path)

    # 绝对路径直接用；相对路径则相对 run.py 所在的项目根目录
    if not path.is_absolute():
        # run.py 启动时已将项目根目录加入 sys.path[0]，直接取用
        import sys
        project_root = Path(sys.path[0]) if sys.path else Path.cwd()
        path = project_root / frame_path

    path = path.resolve()

    if not path.exists():
        logger.warning(f"帧图片不存在: {path}")
        # 兜底：用文件名在 data/processed 下全局搜索
        import sys
        project_root = Path(sys.path[0]) if sys.path else Path.cwd()
        filename = Path(frame_path).name
        candidates = list((project_root / "data" / "processed").rglob(filename))
        if candidates:
            path = candidates[0].resolve()
            logger.info(f"兜底找到: {path}")
        else:
            return jsonify({"error": f"图片不存在: {frame_path}"}), 404

    suffix = path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".bmp": "image/bmp"}
    mime = mime_map.get(suffix, "image/jpeg")

    return send_file(str(path), mimetype=mime)


# ----------------------------------------------------------------
#  GET /api/data/video_file/<video_id>  视频文件流（支持Range）
# ----------------------------------------------------------------

@data_bp.route("/video_file/<int:video_id>", methods=["GET"])
def stream_video_file(video_id: int):
    """
    提供视频文件的 HTTP Range 支持，让前端 <video> 标签可以：
    进度条拖动 / 快进后退 / 正常播放
    """
    try:
        from backend.database.db import get_session
        from backend.database.models import VideoMetadata

        session = get_session()
        try:
            video = session.query(VideoMetadata).filter_by(video_id=video_id).first()
            if not video:
                return jsonify({"error": "视频不存在"}), 404
            file_path = Path(video.file_path)
        finally:
            session.close()

        if not file_path.exists():
            return jsonify({"error": f"视频文件不存在: {file_path}"}), 404

        file_size = file_path.stat().st_size
        range_header = request.headers.get("Range", None)

        mime_map = {
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
        }
        mime = mime_map.get(file_path.suffix.lower(), "video/mp4")

        # 无 Range 请求：直接返回整个文件（支持浏览器缓存）
        if not range_header:
            response = send_file(str(file_path), mimetype=mime, conditional=True)
            response.headers["Accept-Ranges"] = "bytes"
            return response

        # 解析 Range: bytes=start-end
        m = re.search(r"bytes=(\d+)-(\d*)", range_header)
        if not m:
            return Response(status=416)  # Range Not Satisfiable

        start  = int(m.group(1))
        end    = int(m.group(2)) if m.group(2) else file_size - 1
        end    = min(end, file_size - 1)

        if start > end or start >= file_size:
            return Response(
                status=416,
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        length = end - start + 1

        def generate(path_str, start, length, chunk=512 * 1024):
            with open(path_str, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        resp = Response(
            generate(str(file_path), start, length),
            status=206,
            mimetype=mime,
        )
        resp.headers["Content-Range"]  = f"bytes {start}-{end}/{file_size}"
        resp.headers["Accept-Ranges"]  = "bytes"
        resp.headers["Content-Length"] = str(length)
        resp.headers["Cache-Control"]  = "no-cache"
        # 让浏览器 JS 能读到这些头（CORS 限制下必须显式暴露）
        resp.headers["Access-Control-Expose-Headers"] = \
            "Content-Range, Accept-Ranges, Content-Length, Content-Type"
        return resp

    except Exception as e:
        logger.error(f"视频流失败: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/data/upload
# ----------------------------------------------------------------

@data_bp.route("/upload", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return jsonify({"success": False, "error": "请上传视频文件"}), 400

    file = request.files["video"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXT:
        return jsonify({"success": False, "error": f"不支持的视频格式: {suffix}"}), 400

    camera_id       = int(request.form.get("camera_id", 1))
    camera_location = request.form.get("camera_location", "未知位置")
    interval        = int(request.form.get("interval", 10))

    save_name = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOAD_DIR / save_name
    file.save(str(save_path))
    logger.info(f"视频已保存: {save_path}")

    try:
        from backend.preprocessing.video_processor import VideoProcessor
        processor = VideoProcessor(device="cuda")
        result = processor.process_video(
            video_path=save_path,
            output_base_dir="data/processed",
            interval=interval,
        )
        from backend.database.ingest import ingest
        video_id = ingest(
            pickle_path=result["output_file"],
            video_path=str(save_path),
            camera_id=camera_id,
            camera_location=camera_location,
        )
        _rebuild_search_index()
        return jsonify({
            "success": True,
            "video_id": video_id,
            "keyframes": result["keyframes"],
            "total_persons": result["total_persons"],
            "camera_location": camera_location,
        })
    except Exception as e:
        logger.error(f"视频处理失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  GET /api/data/videos
# ----------------------------------------------------------------

@data_bp.route("/videos", methods=["GET"])
def list_videos():
    try:
        from backend.database.db import get_session
        from backend.database.models import VideoMetadata, KeyFrame, DetectedObject, Trajectory
        from sqlalchemy import func

        session = get_session()
        try:
            videos = session.query(VideoMetadata).order_by(
                VideoMetadata.created_at.desc()).all()
            result = []
            for v in videos:
                frame_count = session.query(func.count(KeyFrame.frame_id)).filter_by(
                    video_id=v.video_id).scalar()
                object_count = (
                    session.query(func.count(DetectedObject.object_id))
                    .join(KeyFrame, DetectedObject.frame_id == KeyFrame.frame_id)
                    .filter(KeyFrame.video_id == v.video_id).scalar()
                )
                traj = session.query(Trajectory).filter_by(video_id=v.video_id).first()
                result.append({
                    "video_id":        v.video_id,
                    "file_path":       v.file_path,
                    "duration":        v.duration,
                    "camera_id":       v.camera_id,
                    "camera_location": traj.camera_location if traj else "未知位置",
                    "frame_count":     frame_count,
                    "object_count":    object_count,
                    "created_at":      v.created_at.isoformat() if v.created_at else None,
                })
            return jsonify({"success": True, "videos": result})
        finally:
            session.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  GET /api/data/videos/<video_id>
# ----------------------------------------------------------------

@data_bp.route("/videos/<int:video_id>", methods=["GET"])
def get_video(video_id: int):
    try:
        from backend.database.db import get_session
        from backend.database.models import VideoMetadata, KeyFrame, DetectedObject, Trajectory

        session = get_session()
        try:
            video = session.query(VideoMetadata).filter_by(video_id=video_id).first()
            if not video:
                return jsonify({"success": False, "error": "视频不存在"}), 404

            keyframes = session.query(KeyFrame).filter_by(video_id=video_id).order_by(
                KeyFrame.frame_time).all()
            traj = session.query(Trajectory).filter_by(video_id=video_id).first()

            frames_data = []
            for kf in keyframes:
                obj_count = session.query(DetectedObject).filter_by(
                    frame_id=kf.frame_id).count()
                frames_data.append({
                    "frame_id":   kf.frame_id,
                    "frame_time": kf.frame_time,
                    "frame_path": kf.frame_path,
                    "obj_count":  obj_count,
                })

            return jsonify({
                "success": True,
                "video": {
                    "video_id":        video.video_id,
                    "file_path":       video.file_path,
                    "duration":        video.duration,
                    "camera_id":       video.camera_id,
                    "camera_location": traj.camera_location if traj else "未知位置",
                    "keyframes":       frames_data,
                }
            })
        finally:
            session.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  POST /api/data/rebuild_index
# ----------------------------------------------------------------

@data_bp.route("/rebuild_index", methods=["POST"])
def rebuild_index():
    try:
        count = _rebuild_search_index()
        return jsonify({"success": True, "indexed_vectors": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  DELETE /api/data/videos/<video_id>
# ----------------------------------------------------------------

@data_bp.route("/videos/<int:video_id>", methods=["DELETE"])
def delete_video(video_id: int):
    try:
        from backend.database.db import get_session
        from backend.database.models import VideoMetadata

        session = get_session()
        try:
            video = session.query(VideoMetadata).filter_by(video_id=video_id).first()
            if not video:
                return jsonify({"success": False, "error": "视频不存在"}), 404
            session.delete(video)
            session.commit()
        finally:
            session.close()

        _rebuild_search_index()
        return jsonify({"success": True, "message": f"视频 {video_id} 已删除"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------
#  内部工具
# ----------------------------------------------------------------

def _rebuild_search_index() -> int:
    from backend.database.db import get_session
    from backend.models.feature_index import FeatureIndex
    from config import FAISS_CONFIG
    import backend.api.routes.search as search_module

    search_module._feature_index = None
    session = get_session()
    try:
        index = FeatureIndex(
            dim=FAISS_CONFIG["dim"],
            index_path=FAISS_CONFIG["index_path"],
        )
        count = index.build_from_db(session)
        if count > 0:
            index.save()
        logger.info(f"FAISS 索引重建完成，共 {count} 条向量")
        return count
    finally:
        session.close()
