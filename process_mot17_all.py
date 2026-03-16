#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MOT17 批量处理脚本
功能：将 MOT17 所有场景图片序列 → H.264 视频 → 提取特征 → 入库 → 重建索引

说明：
  MOT17 每个场景有 DPM/FRCNN/SDP 三个版本，图片内容完全相同，
  默认只处理 DPM 版本（7个场景），避免重复入库。
  如需处理全部 21 个序列，设置 ONLY_DPM = False

用法：
  cd c:\\vedio_retrieval_system
  C:/anconda/envs/video_retrieval/python.exe process_mot17_all.py
"""

import os
import sys
import subprocess
import pickle
from pathlib import Path
from tqdm import tqdm

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
sys.path.insert(0, str(Path(__file__).parent))

# ================================================================
#  配置
# ================================================================

MOT17_TRAIN_DIR = Path("data/MOT17/train")   # MOT17 训练集目录
OUTPUT_VIDEOS   = Path("data/videos")         # 视频输出目录
OUTPUT_PROCESSED= Path("data/processed")      # 特征输出目录
FRAME_INTERVAL  = 5                           # 每5秒提取一帧（MOT17视频较短，间隔小一点）
ONLY_DPM        = True                        # True=只处理DPM版本(7个)，False=处理全部21个

# 场景名 → 摄像头位置描述（用于轨迹图显示）
CAMERA_LOCATION_MAP = {
    "MOT17-02": "停车场入口",
    "MOT17-04": "城市街道",
    "MOT17-05": "购物中心",
    "MOT17-09": "行人过街",
    "MOT17-10": "广场中央",
    "MOT17-11": "校园通道",
    "MOT17-13": "室内走廊",
}


# ================================================================
#  步骤1：图片序列 → H.264 视频
# ================================================================

def convert_sequence_to_video(seq_dir: Path, output_video: Path) -> bool:
    """将一个 MOT17 序列的图片转换为 H.264 视频"""
    import cv2

    img_dir = seq_dir / "img1"
    if not img_dir.exists():
        print(f"    ❌ 图片目录不存在: {img_dir}")
        return False

    images = sorted(img_dir.glob("*.jpg"))
    if not images:
        print(f"    ❌ 未找到图片")
        return False

    print(f"    图片数量: {len(images)}")

    # 读取分辨率
    first = cv2.imread(str(images[0]))
    if first is None:
        print(f"    ❌ 无法读取图片")
        return False
    h, w = first.shape[:2]

    # 尝试用 ffmpeg 转为 H.264（浏览器兼容）
    if _convert_with_ffmpeg(images, output_video, w, h):
        return True

    # ffmpeg 失败则用 OpenCV（mp4v，可能浏览器不支持，但功能可用）
    print(f"    ffmpeg 失败，使用 OpenCV 备用方案...")
    return _convert_with_opencv(images, output_video, w, h)


def _convert_with_ffmpeg(images: list, output_video: Path, w: int, h: int) -> bool:
    """用 ffmpeg 将图片列表合成 H.264 视频"""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    # 将图片路径写入临时文件列表（ffmpeg concat demuxer）
    list_file = output_video.parent / f"_imglist_{output_video.stem}.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for img in images:
                # ffmpeg concat 格式
                f.write(f"file '{img.as_posix()}'\n")
                f.write(f"duration 0.033\n")   # 30fps

        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            str(output_video),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0 and output_video.exists() and output_video.stat().st_size > 10000

    except Exception as e:
        print(f"    ffmpeg 异常: {e}")
        return False
    finally:
        if list_file.exists():
            list_file.unlink()


def _convert_with_opencv(images: list, output_video: Path, w: int, h: int) -> bool:
    """用 OpenCV 将图片列表合成视频（备用）"""
    import cv2

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(str(output_video), fourcc, 30, (w, h))
    if not out.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_video), fourcc, 30, (w, h))

    for img_path in tqdm(images, desc="    合成视频", leave=False):
        frame = cv2.imread(str(img_path))
        if frame is not None:
            out.write(frame)
    out.release()
    return output_video.exists() and output_video.stat().st_size > 10000


# ================================================================
#  步骤2：视频 → 特征提取 → 入库
# ================================================================

def process_and_ingest(video_path: Path, camera_id: int, camera_location: str) -> int:
    """对一个视频做特征提取并入库，返回 video_id"""
    from backend.preprocessing.video_processor import VideoProcessor
    from backend.database.ingest import ingest

    # 初始化处理器（只初始化一次，外部传入）
    processor = VideoProcessor(device="cuda")

    print(f"    提取关键帧（间隔 {FRAME_INTERVAL}s）...")
    result = processor.process_video(
        video_path=video_path,
        output_base_dir=str(OUTPUT_PROCESSED),
        interval=FRAME_INTERVAL,
    )
    print(f"    关键帧: {result['keyframes']}  人物目标: {result['total_persons']}")

    print(f"    写入数据库...")
    video_id = ingest(
        pickle_path=result["output_file"],
        video_path=str(video_path),
        camera_id=camera_id,
        camera_location=camera_location,
    )
    print(f"    ✅ 入库完成，video_id={video_id}")
    return video_id


# ================================================================
#  主流程
# ================================================================

def main():
    print("=" * 65)
    print("  MOT17 批量处理脚本")
    print("=" * 65)

    if not MOT17_TRAIN_DIR.exists():
        print(f"❌ MOT17 数据集不存在: {MOT17_TRAIN_DIR.absolute()}")
        return

    OUTPUT_VIDEOS.mkdir(parents=True, exist_ok=True)
    OUTPUT_PROCESSED.mkdir(parents=True, exist_ok=True)

    # 收集需要处理的序列
    all_sequences = sorted([d for d in MOT17_TRAIN_DIR.iterdir() if d.is_dir()])
    if ONLY_DPM:
        sequences = [s for s in all_sequences if s.name.endswith("-DPM")]
        print(f"模式：只处理 DPM 版本（共 {len(sequences)} 个场景）")
    else:
        sequences = all_sequences
        print(f"模式：处理全部序列（共 {len(sequences)} 个）")

    print(f"\n待处理序列：")
    for s in sequences:
        scene = "-".join(s.name.split("-")[:2])   # MOT17-02
        loc   = CAMERA_LOCATION_MAP.get(scene, f"摄像头-{scene}")
        video_exists = (OUTPUT_VIDEOS / f"{s.name}.mp4").exists()
        print(f"  {'✅' if video_exists else '⬜'} {s.name}  →  {loc}")

    print()

    # 初始化 VideoProcessor（只加载一次模型，避免重复加载）
    print("加载 AI 模型（YOLOv8 + CLIP）...")
    from backend.preprocessing.video_processor import VideoProcessor
    from backend.database.ingest import ingest as db_ingest
    from backend.database.db import get_session
    from backend.database.models import VideoMetadata

    processor = VideoProcessor(device="cuda")
    print("✅ 模型加载完成\n")

    success_list = []
    skip_list    = []
    fail_list    = []

    for idx, seq_dir in enumerate(sequences):
        seq_name = seq_dir.name
        scene    = "-".join(seq_name.split("-")[:2])
        camera_id       = idx + 1
        camera_location = CAMERA_LOCATION_MAP.get(scene, f"摄像头-{scene}")
        video_path      = OUTPUT_VIDEOS / f"{seq_name}.mp4"

        print(f"\n[{idx+1}/{len(sequences)}] {seq_name}  →  {camera_location}")
        print("-" * 55)

        # ── 检查是否已经入库 ──
        session = get_session()
        try:
            existing = session.query(VideoMetadata).filter_by(
                file_path=str(video_path)).first()
        finally:
            session.close()

        if existing:
            print(f"  ⏭️  已入库（video_id={existing.video_id}），跳过")
            skip_list.append(seq_name)
            continue

        try:
            # ── 步骤1：转换视频 ──
            if video_path.exists():
                print(f"  视频已存在，跳过转换")
            else:
                print(f"  转换图片序列 → H.264 视频...")
                ok = convert_sequence_to_video(seq_dir, video_path)
                if not ok:
                    print(f"  ❌ 视频转换失败，跳过")
                    fail_list.append(seq_name)
                    continue
                size_mb = video_path.stat().st_size / 1024 / 1024
                print(f"  ✅ 视频创建完成 ({size_mb:.1f} MB)")

            # ── 步骤2：特征提取 + 入库 ──
            print(f"  提取特征并入库（摄像头位置：{camera_location}）...")
            result = processor.process_video(
                video_path=video_path,
                output_base_dir=str(OUTPUT_PROCESSED),
                interval=FRAME_INTERVAL,
            )
            print(f"  关键帧: {result['keyframes']}  人物目标: {result['total_persons']}")

            video_id = db_ingest(
                pickle_path=result["output_file"],
                video_path=str(video_path),
                camera_id=camera_id,
                camera_location=camera_location,
            )
            print(f"  ✅ 入库完成，video_id={video_id}")
            success_list.append(seq_name)

        except Exception as e:
            print(f"  ❌ 处理失败: {e}")
            import traceback; traceback.print_exc()
            fail_list.append(seq_name)

    # ── 汇总 ──
    print("\n" + "=" * 65)
    print("  处理完成！汇总")
    print("=" * 65)
    print(f"  ✅ 成功处理: {len(success_list)} 个")
    print(f"  ⏭️  已跳过:   {len(skip_list)} 个（已入库）")
    print(f"  ❌ 失败:     {len(fail_list)} 个")

    if success_list:
        print(f"\n成功列表: {', '.join(success_list)}")
    if fail_list:
        print(f"\n失败列表: {', '.join(fail_list)}")

    if success_list:
        print("\n✅ 所有数据已入库，FAISS 索引已自动重建")
        print("   重启后端后即可在系统中搜索所有摄像头的人物轨迹")


if __name__ == "__main__":
    main()
