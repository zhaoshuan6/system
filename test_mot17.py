#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用MOT17数据集测试视频预处理模块
"""

import os
import sys
from pathlib import Path

# === 设置环境变量 ===
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# === 添加项目根目录到Python路径 ===
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# === 标准方式导入 ===
from backend.preprocessing.video_processor import VideoProcessor
print("✅ VideoProcessor 导入成功！")


def convert_mot17_to_video():
    """将MOT17的图片序列转换为视频"""
    import cv2
    from tqdm import tqdm

    mot17_dir = Path("data/MOT17/train")

    if not mot17_dir.exists():
        print(f"❌ MOT17数据集不存在，预期路径: {mot17_dir.absolute()}")
        print("请先下载：https://motchallenge.net/data/MOT17/")
        return None

    sequences = sorted([d for d in mot17_dir.iterdir() if d.is_dir()])
    if not sequences:
        print("❌ 未找到MOT17序列")
        return None

    # 使用第一个序列
    seq = sequences[0]
    print(f"\n使用序列: {seq.name}")

    img_dir = seq / "img1"
    if not img_dir.exists():
        print(f"❌ 图片目录不存在: {img_dir}")
        return None

    images = sorted(img_dir.glob("*.jpg"))
    if not images:
        print("❌ 未找到图片")
        return None

    print(f"图片数量: {len(images)}")

    output_dir = Path("data/videos")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_video = output_dir / f"{seq.name}.mp4"

    if output_video.exists():
        print(f"✅ 视频已存在: {output_video}")
        return output_video

    print(f"\n📹 创建视频: {output_video.name}")

    first_img = cv2.imread(str(images[0]))
    if first_img is None:
        print(f"❌ 无法读取图片: {images[0]}")
        return None
    height, width = first_img.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_video), fourcc, 30, (width, height))

    for img_path in tqdm(images, desc="创建视频"):
        frame = cv2.imread(str(img_path))
        if frame is not None:
            out.write(frame)

    out.release()
    print(f"✅ 视频创建完成: {output_video}")
    return output_video


def main():
    """主测试函数"""
    print("=" * 70)
    print("  MOT17数据集预处理测试")
    print("=" * 70)

    # 检查MOT17数据集
    mot17_dir = Path("data/MOT17/train")
    if not mot17_dir.exists():
        print(f"\n❌ MOT17数据集不存在，预期路径: {mot17_dir.absolute()}")
        print("请先下载：https://motchallenge.net/data/MOT17/")
        print(f"然后解压到: {mot17_dir.parent.absolute()}")
        return

    # 将MOT17图片序列转换为视频
    video_path = convert_mot17_to_video()
    if video_path is None:
        return

    # 初始化视频处理器
    print("\n" + "=" * 70)
    print("  初始化视频处理器")
    print("=" * 70)
    processor = VideoProcessor(device="cuda")

    # 处理视频
    print("\n" + "=" * 70)
    print("  开始处理视频")
    print("=" * 70)
    result = processor.process_video(
        video_path=video_path,
        output_base_dir="data/processed",
        interval=10  # 每10秒提取一帧
    )

    print("\n" + "=" * 70)
    print("  处理完成")
    print("=" * 70)
    print(f"\n视频名称: {result['video_name']}")
    print(f"关键帧数: {result['keyframes']}")
    print(f"检测人物: {result['total_persons']}")
    print(f"输出文件: {result['output_file']}")

    # 查看结果
    print("\n" + "=" * 70)
    print("  查看处理结果")
    print("=" * 70)

    import pickle
    with open(result['output_file'], 'rb') as f:
        processed_data = pickle.load(f)

    print(f"\n处理了 {len(processed_data)} 帧")

    for i, frame_data in enumerate(processed_data[:3]):
        print(f"\n帧 {i + 1}:")
        print(f"  图片: {Path(frame_data['frame_path']).name}")
        print(f"  时间戳: {frame_data['timestamp']:.1f}s")
        print(f"  检测到的人物: {len(frame_data['persons'])}")

        for j, person in enumerate(frame_data['persons'][:3]):
            print(f"    人物 {j + 1}:")
            print(f"      位置: ({person['bbox'][0]}, {person['bbox'][1]}) - ({person['bbox'][2]}, {person['bbox'][3]})")
            print(f"      置信度: {person['confidence']:.2%}")
            print(f"      特征维度: {person['features'].shape}")

    print("\n✅ 测试完成！")


if __name__ == "__main__":
    main()
