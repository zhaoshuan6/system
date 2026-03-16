#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频转码脚本
将 data/videos 目录下所有视频转为 H.264 编码（浏览器兼容）

用法：
    python transcode_videos.py
"""

import os
import sys
import subprocess
from pathlib import Path

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
sys.path.insert(0, str(Path(__file__).parent))


def check_codec(video_path: str) -> str:
    """检查视频编码格式"""
    import cv2
    cap = cv2.VideoCapture(video_path)
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc = fourcc_int.to_bytes(4, 'little').decode('utf-8', errors='replace')
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fourcc, fps, w, h, frames


def transcode_with_ffmpeg(input_path: Path, output_path: Path) -> bool:
    """用 ffmpeg 转码为 H.264"""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"  # 系统 PATH 中的 ffmpeg

    cmd = [
        ffmpeg_exe,
        "-y",                        # 覆盖已有文件
        "-i", str(input_path),       # 输入
        "-c:v", "libx264",           # H.264 编码
        "-preset", "fast",           # 编码速度
        "-crf", "23",                # 质量（18=高质量, 28=低质量）
        "-pix_fmt", "yuv420p",       # 兼容性最好的像素格式
        "-movflags", "+faststart",   # 支持网络流式播放（进度条seek）
        "-an",                       # 无音频（监控视频通常没有）
        str(output_path),
    ]

    print(f"  执行: {' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return True
    else:
        print(f"  ffmpeg 失败:\n{result.stderr[-500:]}")
        return False


def transcode_with_opencv(input_path: Path, output_path: Path) -> bool:
    """用 OpenCV 转码（备用方案，兼容性差一些）"""
    import cv2
    from tqdm import tqdm

    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # avc1 = H.264，Windows 下需要安装编码器
    # 备用用 H264
    fourcc = cv2.VideoWriter_fourcc(*'H264')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

    if not out.isOpened():
        # 再试 avc1
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

    if not out.isOpened():
        print("  OpenCV 也无法创建 H.264 编码器")
        cap.release()
        return False

    for _ in tqdm(range(total), desc="  转码"):
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)

    cap.release()
    out.release()
    return output_path.exists() and output_path.stat().st_size > 1000


def update_db_path(old_path: str, new_path: str):
    """更新数据库中的视频路径"""
    from backend.database.db import get_session
    from backend.database.models import VideoMetadata

    session = get_session()
    try:
        video = session.query(VideoMetadata).filter_by(file_path=old_path).first()
        if video:
            video.file_path = new_path
            session.commit()
            print(f"  ✅ 数据库路径已更新: {Path(new_path).name}")
        else:
            print(f"  ⚠️  数据库中未找到该视频，路径未更新")
    finally:
        session.close()


def main():
    print("=" * 55)
    print("  视频转码工具（mp4v → H.264）")
    print("=" * 55)

    videos_dir = Path("data/videos")
    if not videos_dir.exists():
        print("❌ data/videos 目录不存在")
        return

    video_files = list(videos_dir.glob("*.mp4")) + list(videos_dir.glob("*.avi"))
    if not video_files:
        print("❌ 未找到视频文件")
        return

    for video_path in video_files:
        print(f"\n处理: {video_path.name}")

        codec, fps, w, h, frames = check_codec(str(video_path))
        print(f"  编码: {codec}  {w}x{h}  {fps:.1f}fps  {frames}帧")

        # 已经是 H.264 则跳过
        if codec.lower() in ('avc1', 'h264', 'x264'):
            print("  ✅ 已是 H.264，无需转码")
            continue

        # 输出路径：原文件名 + _h264 后缀，确认无误后再替换
        out_path = video_path.parent / (video_path.stem + "_h264.mp4")

        print(f"  转码为: {out_path.name}")

        # 优先用 ffmpeg（质量更好），失败则用 OpenCV
        success = transcode_with_ffmpeg(video_path, out_path)
        if not success:
            print("  ffmpeg 失败，尝试 OpenCV...")
            success = transcode_with_opencv(video_path, out_path)

        if success:
            size_mb = out_path.stat().st_size / 1024 / 1024
            print(f"  ✅ 转码成功，文件大小: {size_mb:.1f} MB")

            # 备份原文件，用新文件替换
            backup_path = video_path.parent / (video_path.stem + "_mp4v_backup.mp4")
            video_path.rename(backup_path)
            out_path.rename(video_path)
            print(f"  原文件已备份为: {backup_path.name}")
            print(f"  新文件已命名为: {video_path.name}")

            # 数据库路径不变（文件名相同），无需更新
        else:
            print(f"  ❌ 转码失败")

    print("\n" + "=" * 55)
    print("  转码完成！重启后端后视频即可在浏览器正常播放")
    print("=" * 55)


if __name__ == "__main__":
    main()
