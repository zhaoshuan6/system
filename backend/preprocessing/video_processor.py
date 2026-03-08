#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频预处理模块
功能：
  1. 从视频中按时间间隔提取关键帧
  2. 使用 YOLOv8 检测每帧中的人物
  3. 使用 CLIP 提取每个人物裁剪图的特征向量
  4. 将结果保存到数据库 + pickle 文件
"""

import os
import pickle
import logging
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    视频处理器：提取帧 → 检测人物 → 提取CLIP特征

    使用示例:
        processor = VideoProcessor(device="cuda")
        result = processor.process_video(
            video_path="data/videos/MOT17-02-FRCNN.mp4",
            output_base_dir="data/processed",
            interval=10
        )
    """

    def __init__(self, device: str = "cuda"):
        """
        初始化视频处理器

        Args:
            device: 运行设备，"cuda" 或 "cpu"
        """
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA 不可用，自动切换到 CPU")
            device = "cpu"

        self.device = device
        logger.info(f"使用设备: {self.device}")

        self._detector = None
        self._clip_model = None
        self._clip_preprocess = None

        self._load_detector()
        self._load_clip()

    # ------------------------------------------------------------------ #
    #  模型加载
    # ------------------------------------------------------------------ #

    def _load_detector(self):
        """加载 YOLOv8 人物检测模型"""
        try:
            from ultralytics import YOLO
            logger.info("加载 YOLOv8 检测模型...")
            self._detector = YOLO("yolov8n.pt")
            logger.info("✅ YOLOv8 加载成功")
        except ImportError:
            raise ImportError("未安装 ultralytics，请运行: pip install ultralytics")
        except Exception as e:
            raise RuntimeError(f"YOLOv8 加载失败: {e}")

    def _load_clip(self):
        """加载 CLIP 特征提取模型"""
        try:
            import clip
            logger.info("加载 CLIP 模型 (ViT-B/32)...")
            self._clip_model, self._clip_preprocess = clip.load("ViT-B/32", device=self.device)
            self._clip_model.eval()
            logger.info("✅ CLIP 加载成功")
        except ImportError:
            raise ImportError("未安装 clip，请运行: pip install git+https://github.com/openai/CLIP.git")
        except Exception as e:
            raise RuntimeError(f"CLIP 加载失败: {e}")

    # ------------------------------------------------------------------ #
    #  主流程
    # ------------------------------------------------------------------ #

    def process_video(
        self,
        video_path,
        output_base_dir: str = "data/processed",
        interval: int = 10,
    ) -> dict:
        """
        处理视频：提取关键帧 → 检测人物 → 提取特征 → 保存结果

        Args:
            video_path:       视频文件路径（str 或 Path）
            output_base_dir:  结果输出根目录
            interval:         关键帧提取间隔（秒）

        Returns:
            dict:
                video_name    - 视频文件名（不含扩展名）
                keyframes     - 提取的关键帧数量
                total_persons - 检测到的人物总数
                output_file   - 结果 pickle 文件路径
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        video_name = video_path.stem
        output_dir = Path(output_base_dir) / video_name
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始处理视频: {video_path.name}")

        # 1. 提取关键帧
        frame_paths, frame_timestamps = self._extract_keyframes(video_path, frames_dir, interval)
        logger.info(f"提取关键帧: {len(frame_paths)} 帧")

        # 2. 对每帧检测人物并提取特征
        processed_data = []
        total_persons = 0

        for idx, (frame_path, timestamp) in enumerate(zip(frame_paths, frame_timestamps)):
            logger.info(f"处理帧 {idx + 1}/{len(frame_paths)}: {frame_path.name}")
            frame_bgr = cv2.imread(str(frame_path))
            if frame_bgr is None:
                logger.warning(f"无法读取帧: {frame_path}")
                continue

            persons = self._detect_and_extract(frame_bgr)
            total_persons += len(persons)

            processed_data.append({
                "frame_path": str(frame_path),
                "timestamp":  timestamp,        # 单位：秒
                "persons":    persons,
            })

        # 3. 保存结果为 pickle
        output_file = output_dir / f"{video_name}_processed.pkl"
        with open(output_file, "wb") as f:
            pickle.dump(processed_data, f)

        logger.info(f"✅ 处理完成，结果保存至: {output_file}")

        return {
            "video_name":    video_name,
            "keyframes":     len(frame_paths),
            "total_persons": total_persons,
            "output_file":   str(output_file),
        }

    # ------------------------------------------------------------------ #
    #  关键帧提取
    # ------------------------------------------------------------------ #

    def _extract_keyframes(self, video_path: Path, frames_dir: Path, interval: int):
        """
        按时间间隔从视频中提取关键帧

        Returns:
            (frame_paths, timestamps): 帧文件路径列表 和 对应时间戳（秒）列表
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30
            logger.warning("无法读取视频 FPS，默认使用 30")

        frame_interval = max(1, int(fps * interval))
        frame_paths = []
        timestamps = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / fps
                save_path = frames_dir / f"frame_{frame_idx:06d}_t{int(timestamp):04d}s.jpg"
                cv2.imwrite(str(save_path), frame)
                frame_paths.append(save_path)
                timestamps.append(timestamp)

            frame_idx += 1

        cap.release()
        return frame_paths, timestamps

    # ------------------------------------------------------------------ #
    #  人物检测 + CLIP特征提取
    # ------------------------------------------------------------------ #

    def _detect_and_extract(self, frame_bgr: np.ndarray) -> list:
        """
        在单帧中检测人物并用 CLIP 提取特征

        Args:
            frame_bgr: BGR 格式的图像（numpy array）

        Returns:
            list[dict]: 每个人物的信息，包含 bbox、confidence、features
        """
        persons = []

        # --- YOLOv8 检测人物 (class 0 = person) ---
        results = self._detector(frame_bgr, classes=[0], verbose=False)
        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            return persons

        h, w = frame_bgr.shape[:2]
        crops_pil = []
        valid_boxes = []

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])

            if conf < 0.3:
                continue

            # 边界裁剪保护
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if (x2 - x1) < 10 or (y2 - y1) < 10:
                continue

            # BGR → RGB → PIL
            crop_rgb = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
            crops_pil.append(Image.fromarray(crop_rgb))
            valid_boxes.append((x1, y1, x2, y2, conf))

        if not crops_pil:
            return persons

        # --- CLIP 批量特征提取 ---
        try:
            image_tensors = torch.stack(
                [self._clip_preprocess(img) for img in crops_pil]
            ).to(self.device)

            with torch.no_grad():
                features = self._clip_model.encode_image(image_tensors)
                # L2 归一化，便于后续余弦相似度检索
                features = features / features.norm(dim=-1, keepdim=True)
                features = features.cpu().numpy()  # shape: (N, 512)

        except Exception as e:
            logger.warning(f"CLIP 特征提取失败: {e}")
            return persons

        for (x1, y1, x2, y2, conf), feat in zip(valid_boxes, features):
            persons.append({
                "bbox":       [x1, y1, x2, y2],
                "confidence": conf,
                "features":   feat,   # numpy array, shape (512,)
            })

        return persons
