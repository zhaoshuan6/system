#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频人物检索系统 — 量化评测脚本
====================================
使用 MOT17 数据集的 ground truth 标注评估检索性能。

评测指标：
  - Rank-1 / Rank-5 / Rank-10 Accuracy
  - mAP (mean Average Precision)
  - Precision@1 / Precision@5 / Precision@10

评测方式（Gallery-Query Split）：
  对每个序列中每个行人 ID：
    · Query  : 该 ID 在视频前半段的第一个高置信度出现
    · Gallery: 该 ID 在视频后半段的所有出现 + 其他 ID 的出现

用法：
  python evaluate_retrieval.py
  python evaluate_retrieval.py --seq MOT17-02-DPM       # 只评测单个序列
  python evaluate_retrieval.py --min_frames 20          # 过滤出现帧数太少的人
  python evaluate_retrieval.py --output report.txt      # 保存报告到文件
"""

import os
import sys
import cv2
import numpy as np
import torch
import argparse
import logging
from pathlib import Path
from collections import defaultdict

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# MOT17 ground truth 列索引
COL_FRAME   = 0
COL_ID      = 1
COL_X       = 2
COL_Y       = 3
COL_W       = 4
COL_H       = 5
COL_CONF    = 6   # 1=有效标注, 0=忽略区域
COL_CLASS   = 7   # 1=pedestrian, 2=person on vehicle, 7=distractor ...
COL_VIS     = 8   # 可见度 0~1

SEQUENCES = [
    "MOT17-02-DPM",
    "MOT17-04-DPM",
    "MOT17-05-DPM",
    "MOT17-09-DPM",
    "MOT17-10-DPM",
    "MOT17-11-DPM",
    "MOT17-13-DPM",
]


# ================================================================
#  CLIP 模型（单例）
# ================================================================

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


def extract_feature(img_bgr: np.ndarray) -> np.ndarray:
    """从 BGR 图像提取 CLIP 特征（512维，L2归一化）"""
    from PIL import Image
    model, preprocess, device = get_clip()
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    tensor = preprocess(pil_img).unsqueeze(0).to(device)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]


# ================================================================
#  数据加载
# ================================================================

def load_gt(gt_path: Path) -> dict:
    """
    读取 gt.txt，返回 {person_id: [(frame, x, y, w, h, vis), ...]}
    只保留行人类别（class=7）且标注有效（conf=1）的记录
    """
    tracks = defaultdict(list)
    with open(gt_path) as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 9:
                continue
            frame = int(parts[COL_FRAME])
            pid   = int(parts[COL_ID])
            x, y, w, h = int(float(parts[COL_X])), int(float(parts[COL_Y])), \
                          int(float(parts[COL_W])), int(float(parts[COL_H]))
            conf  = int(parts[COL_CONF])
            cls   = int(parts[COL_CLASS])
            vis   = float(parts[COL_VIS])

            if conf != 1 or cls != 1:   # 只取有效行人标注（class=1 为行人）
                continue
            tracks[pid].append((frame, x, y, w, h, vis))

    # 按帧号排序
    for pid in tracks:
        tracks[pid].sort(key=lambda t: t[0])
    return dict(tracks)


def crop_person(frame_img: np.ndarray, x, y, w, h, margin=0.1) -> np.ndarray:
    """裁剪人物区域，并加一点边距"""
    H, W = frame_img.shape[:2]
    mx = int(w * margin)
    my = int(h * margin)
    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(W, x + w + mx)
    y2 = min(H, y + h + my)
    crop = frame_img[y1:y2, x1:x2]
    if crop.size == 0:
        return frame_img[max(0,y):max(0,y)+max(1,h), max(0,x):max(0,x)+max(1,w)]
    return crop


# ================================================================
#  Query / Gallery 划分
# ================================================================

def build_query_gallery(tracks: dict, seq_len: int, min_frames: int = 10):
    """
    划分策略：
      - 视频前半段第一个高可见度出现 → query
      - 视频后半段所有出现 → gallery（正样本）
      - 过滤出现帧数不足 min_frames 的人物

    返回:
      queries  : [(pid, frame, x, y, w, h)]
      gallery  : [(pid, frame, x, y, w, h)]
    """
    split = seq_len // 2
    queries = []
    gallery = []

    for pid, records in tracks.items():
        front = [(f, x, y, w, h, v) for f, x, y, w, h, v in records if f <= split]
        back  = [(f, x, y, w, h, v) for f, x, y, w, h, v in records if f > split]

        if len(records) < min_frames:
            continue
        if not front or not back:
            continue

        # Query: 前半段可见度最高的那帧
        best = max(front, key=lambda t: t[5])
        queries.append((pid, best[0], best[1], best[2], best[3], best[4]))

        # Gallery: 后半段每隔 5 帧取一个（避免相邻帧冗余）
        prev_frame = -999
        for f, x, y, w, h, v in back:
            if f - prev_frame >= 5 and v >= 0.3:
                gallery.append((pid, f, x, y, w, h))
                prev_frame = f

    return queries, gallery


# ================================================================
#  特征提取
# ================================================================

def extract_features_for_set(records, img_dir: Path, label: str):
    """
    records: [(pid, frame, x, y, w, h), ...]
    返回: (feats np.ndarray [N,512], pids list[N])
    """
    feats = []
    pids  = []
    total = len(records)
    for i, (pid, frame, x, y, w, h) in enumerate(records):
        img_path = img_dir / f"{frame:06d}.jpg"
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        crop = crop_person(img, x, y, w, h)
        if crop.shape[0] < 10 or crop.shape[1] < 10:
            continue
        feat = extract_feature(crop)
        feats.append(feat)
        pids.append(pid)
        if (i + 1) % 20 == 0 or (i + 1) == total:
            logger.info(f"  [{label}] {i+1}/{total}")
    return np.array(feats, dtype=np.float32), pids


# ================================================================
#  指标计算
# ================================================================

def compute_metrics(query_feats, query_pids, gallery_feats, gallery_pids, topk=(1, 5, 10)):
    """
    计算 Rank-K Accuracy 和 mAP。
    使用余弦相似度（特征已 L2 归一化，内积 = 余弦相似度）。
    """
    # 相似度矩阵 [Q, G]
    sim = query_feats @ gallery_feats.T  # cosine similarity

    max_k = max(topk)
    rank_hits   = {k: 0 for k in topk}
    ap_list     = []
    precision_k = {k: [] for k in topk}

    for i, qpid in enumerate(query_pids):
        scores = sim[i]

        # 排序（从高到低）
        sorted_idx = np.argsort(-scores)
        sorted_pids = [gallery_pids[j] for j in sorted_idx]

        # 正样本标记（gallery 中与 query 同 ID，但排除 query 本身对应帧）
        positives = [1 if p == qpid else 0 for p in sorted_pids]

        n_pos = sum(positives)
        if n_pos == 0:
            continue   # 该 query 在 gallery 中没有正样本，跳过

        # Rank-K Accuracy
        for k in topk:
            if any(positives[:k]):
                rank_hits[k] += 1

        # Precision@K
        for k in topk:
            hits = sum(positives[:k])
            precision_k[k].append(hits / k)

        # Average Precision
        hit_count = 0
        ap = 0.0
        for rank, pos in enumerate(positives, 1):
            if pos:
                hit_count += 1
                ap += hit_count / rank
        ap /= n_pos
        ap_list.append(ap)

    n_queries = len(ap_list)
    if n_queries == 0:
        return {}

    results = {
        "n_queries": n_queries,
        "mAP": np.mean(ap_list) * 100,
    }
    for k in topk:
        results[f"Rank-{k}"]       = rank_hits[k] / n_queries * 100
        results[f"Precision@{k}"]  = np.mean(precision_k[k]) * 100

    return results


# ================================================================
#  单序列评测
# ================================================================

def evaluate_sequence(seq_name: str, mot17_root: Path, min_frames: int) -> dict | None:
    seq_dir = mot17_root / "train" / seq_name
    gt_path = seq_dir / "gt" / "gt.txt"
    img_dir = seq_dir / "img1"

    if not gt_path.exists():
        logger.warning(f"找不到 gt.txt: {gt_path}")
        return None

    # 读取序列信息
    seq_info = {}
    info_path = seq_dir / "seqinfo.ini"
    if info_path.exists():
        for line in info_path.read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                seq_info[k.strip()] = v.strip()
    seq_len = int(seq_info.get("seqLength", 600))

    logger.info(f"\n{'='*50}")
    logger.info(f"序列: {seq_name}  (共 {seq_len} 帧)")

    tracks = load_gt(gt_path)
    logger.info(f"  行人总数: {len(tracks)}")

    queries, gallery = build_query_gallery(tracks, seq_len, min_frames)
    logger.info(f"  Query数: {len(queries)}, Gallery数: {len(gallery)}")

    if len(queries) < 2 or len(gallery) < 2:
        logger.warning(f"  样本不足，跳过此序列")
        return None

    logger.info("  提取 Query 特征...")
    q_feats, q_pids = extract_features_for_set(queries, img_dir, "Query")

    logger.info("  提取 Gallery 特征...")
    g_feats, g_pids = extract_features_for_set(gallery, img_dir, "Gallery")

    if len(q_feats) == 0 or len(g_feats) == 0:
        logger.warning("  特征提取失败，跳过")
        return None

    metrics = compute_metrics(q_feats, q_pids, g_feats, g_pids)
    metrics["sequence"] = seq_name
    metrics["seq_len"]  = seq_len
    return metrics


# ================================================================
#  主函数
# ================================================================

def print_report(all_metrics: list, output_file: str = None):
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  视频人物检索系统 — 检索性能评测报告")
    lines.append("  数据集: MOT17   模型: CLIP ViT-B/32")
    lines.append("=" * 60)

    # 逐序列结果
    lines.append(f"\n{'序列':<20} {'Rank-1':>7} {'Rank-5':>7} {'Rank-10':>8} {'mAP':>7} {'P@1':>7} {'Query数':>8}")
    lines.append("-" * 70)
    for m in all_metrics:
        lines.append(
            f"{m['sequence']:<20} "
            f"{m.get('Rank-1', 0):>6.1f}% "
            f"{m.get('Rank-5', 0):>6.1f}% "
            f"{m.get('Rank-10', 0):>7.1f}% "
            f"{m.get('mAP', 0):>6.1f}% "
            f"{m.get('Precision@1', 0):>6.1f}% "
            f"{m.get('n_queries', 0):>7}"
        )

    # 均值
    if len(all_metrics) > 1:
        lines.append("-" * 70)
        keys = ["Rank-1", "Rank-5", "Rank-10", "mAP", "Precision@1"]
        avgs = {k: np.mean([m[k] for m in all_metrics if k in m]) for k in keys}
        total_q = sum(m.get("n_queries", 0) for m in all_metrics)
        lines.append(
            f"{'平均 (Mean)':<20} "
            f"{avgs['Rank-1']:>6.1f}% "
            f"{avgs['Rank-5']:>6.1f}% "
            f"{avgs['Rank-10']:>7.1f}% "
            f"{avgs['mAP']:>6.1f}% "
            f"{avgs['Precision@1']:>6.1f}% "
            f"{total_q:>7}"
        )

    lines.append("")
    lines.append("指标说明:")
    lines.append("  Rank-K      : top-K 结果中包含正确人物的查询比例")
    lines.append("  mAP         : 所有查询的平均精度均值（综合排序质量）")
    lines.append("  Precision@K : top-K 结果中正确人物占比的均值")
    lines.append("=" * 60)
    lines.append("")

    report = "\n".join(lines)
    print(report)

    if output_file:
        Path(output_file).write_text(report, encoding="utf-8")
        print(f"报告已保存至: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="视频人物检索系统评测")
    parser.add_argument("--mot17",      default="data/MOT17", help="MOT17 数据集根目录")
    parser.add_argument("--seq",        default=None,         help="只评测指定序列，如 MOT17-02-DPM")
    parser.add_argument("--min_frames", type=int, default=15, help="最少出现帧数阈值")
    parser.add_argument("--output",     default=None,         help="报告输出文件路径")
    args = parser.parse_args()

    mot17_root = Path(args.mot17)
    if not mot17_root.exists():
        logger.error(f"找不到 MOT17 数据集目录: {mot17_root}")
        sys.exit(1)

    seqs = [args.seq] if args.seq else SEQUENCES

    all_metrics = []
    for seq in seqs:
        m = evaluate_sequence(seq, mot17_root, args.min_frames)
        if m:
            all_metrics.append(m)

    if not all_metrics:
        logger.error("没有可用的评测结果")
        sys.exit(1)

    print_report(all_metrics, args.output)


if __name__ == "__main__":
    main()
