#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时监控路由
  GET  /api/monitor/stream          - 视频流（MJPEG）
  GET  /api/monitor/sources         - 获取可用视频源列表
  POST /api/monitor/set_source      - 切换视频源
  GET  /api/monitor/status          - 当前监控状态
"""

import cv2
import time
import logging
import threading
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)
monitor_bp = Blueprint("monitor", __name__)


# ----------------------------------------------------------------
#  视频源管理器（单例）
# ----------------------------------------------------------------

class VideoSourceManager:
    """
    管理当前活跃的视频源，支持：
      - 本地摄像头（camera_index: int）
      - 本地视频文件（file_path: str）
    线程安全地读取帧。
    """

    def __init__(self):
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._source_info = {"type": None, "source": None}
        self._running = False

    def open_camera(self, camera_index: int = 0) -> bool:
        """打开本地摄像头"""
        with self._lock:
            self._release()
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # CAP_DSHOW 在Windows下更稳定
            if not cap.isOpened():
                # 回退到默认后端
                cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                self._cap = cap
                self._running = True
                self._source_info = {"type": "camera", "source": camera_index}
                logger.info(f"✅ 摄像头 {camera_index} 已打开")
                return True
            logger.error(f"❌ 无法打开摄像头 {camera_index}")
            return False

    def open_video(self, file_path: str) -> bool:
        """打开本地视频文件（循环播放）"""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"视频文件不存在: {file_path}")
            return False
        with self._lock:
            self._release()
            cap = cv2.VideoCapture(str(path))
            if cap.isOpened():
                self._cap = cap
                self._running = True
                self._source_info = {"type": "video", "source": str(path)}
                logger.info(f"✅ 视频文件已打开: {path.name}")
                return True
            logger.error(f"❌ 无法打开视频文件: {file_path}")
            return False

    def read_frame(self):
        """
        读取一帧，视频文件到末尾时自动循环。
        返回 (success: bool, frame: np.ndarray)
        """
        with self._lock:
            if self._cap is None or not self._running:
                return False, None

            ret, frame = self._cap.read()

            # 视频文件播放到末尾时循环
            if not ret and self._source_info["type"] == "video":
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()

            return ret, frame

    def get_fps(self) -> float:
        with self._lock:
            if self._cap is None:
                return 25.0
            fps = self._cap.get(cv2.CAP_PROP_FPS)
            return fps if fps > 0 else 25.0

    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._running

    def close(self):
        with self._lock:
            self._release()

    def _release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._running = False
        self._source_info = {"type": None, "source": None}

    @property
    def source_info(self):
        return dict(self._source_info)


# 全局视频源管理器
_source_manager = VideoSourceManager()


# ----------------------------------------------------------------
#  MJPEG 流生成器
# ----------------------------------------------------------------

def _generate_frames(max_fps: int = 25):
    """
    生成 MJPEG 帧序列，供 Flask Response 使用。
    max_fps: 最大帧率，避免 CPU 占用过高
    """
    interval = 1.0 / max_fps

    while True:
        start = time.time()

        if not _source_manager.is_open():
            # 发送一张灰色占位帧
            import numpy as np
            placeholder = np.full((480, 640, 3), 80, dtype='uint8')
            cv2.putText(placeholder, "No Video Source", (160, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
            _, buf = cv2.imencode(".jpg", placeholder)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + buf.tobytes() + b"\r\n")
            time.sleep(0.5)
            continue

        ret, frame = _source_manager.read_frame()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        # 编码为 JPEG
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 80]
        ret, buf = cv2.imencode(".jpg", frame, encode_param)
        if not ret:
            continue

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + buf.tobytes() + b"\r\n")

        # 控制帧率
        elapsed = time.time() - start
        sleep_time = interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)


# ----------------------------------------------------------------
#  路由
# ----------------------------------------------------------------

@monitor_bp.route("/stream")
def stream():
    """
    MJPEG 视频流接口
    前端用法：<img src="http://localhost:5000/api/monitor/stream" />
    """
    return Response(
        _generate_frames(max_fps=25),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@monitor_bp.route("/sources", methods=["GET"])
def get_sources():
    """
    获取可用视频源列表：
    - 检测本地摄像头（0~3号）
    - 列出 data/videos 目录下的视频文件
    """
    sources = []

    # 检测摄像头（快速探测，超时0.5s）
    for i in range(4):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cap.release()
            sources.append({
                "id":    f"camera_{i}",
                "type":  "camera",
                "name":  f"摄像头 {i}",
                "value": i,
            })

    # 列出视频文件
    videos_dir = Path("data/videos")
    if videos_dir.exists():
        for f in sorted(videos_dir.glob("*.mp4")):
            sources.append({
                "id":    f"video_{f.stem}",
                "type":  "video",
                "name":  f.name,
                "value": str(f),
            })
        for f in sorted(videos_dir.glob("*.avi")):
            sources.append({
                "id":    f"video_{f.stem}",
                "type":  "video",
                "name":  f.name,
                "value": str(f),
            })

    return jsonify({"success": True, "sources": sources})


@monitor_bp.route("/set_source", methods=["POST"])
def set_source():
    """
    切换视频源
    请求体（JSON）：
      type   - "camera" 或 "video"
      source - 摄像头序号（int）或视频文件路径（str）
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请提供 JSON 参数"}), 400

    source_type = data.get("type")
    source      = data.get("source")

    if source_type == "camera":
        ok = _source_manager.open_camera(int(source))
    elif source_type == "video":
        ok = _source_manager.open_video(str(source))
    else:
        return jsonify({"success": False, "error": "type 必须为 camera 或 video"}), 400

    if ok:
        return jsonify({
            "success": True,
            "message": f"视频源已切换: {source_type} → {source}",
        })
    else:
        return jsonify({
            "success": False,
            "error": f"无法打开视频源: {source}",
        }), 500


@monitor_bp.route("/status", methods=["GET"])
def status():
    """获取当前监控状态"""
    info = _source_manager.source_info
    return jsonify({
        "success":   True,
        "is_active": _source_manager.is_open(),
        "type":      info.get("type"),
        "source":    info.get("source"),
        "fps":       _source_manager.get_fps(),
    })


@monitor_bp.route("/stop", methods=["POST"])
def stop():
    """停止当前视频流"""
    _source_manager.close()
    return jsonify({"success": True, "message": "监控已停止"})
