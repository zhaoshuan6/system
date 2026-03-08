#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

print("="*60)
print("  最终环境检查")
print("="*60)

results = []

# 1. PyTorch + CUDA
print("\n[1] PyTorch + CUDA")
try:
    import torch
    cuda_ok = torch.cuda.is_available()
    print(f"    版本: {torch.__version__}")
    print(f"    CUDA: {cuda_ok}")
    if cuda_ok:
        print(f"    GPU: {torch.cuda.get_device_name(0)}")
        print(f"    显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    results.append(("PyTorch", cuda_ok))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("PyTorch", False))

# 2. OpenCV
print("\n[2] OpenCV")
try:
    import cv2
    print(f"    版本: {cv2.__version__}")
    results.append(("OpenCV", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("OpenCV", False))

# 3. Faiss
print("\n[3] Faiss")
try:
    import faiss
    gpu_count = faiss.get_num_gpus()
    print(f"    GPU数量: {gpu_count}")
    
    # 简单性能测试
    if gpu_count > 0:
        import numpy as np
        import time
        
        d = 512
        nb = 10000
        nq = 100
        
        xb = np.random.random((nb, d)).astype('float32')
        xq = np.random.random((nq, d)).astype('float32')
        
        # CPU
        index = faiss.IndexFlatL2(d)
        index.add(xb)
        start = time.time()
        D, I = index.search(xq, 5)
        cpu_time = time.time() - start
        
        # GPU
        res = faiss.StandardGpuResources()
        gpu_index = faiss.index_cpu_to_gpu(res, 0, index)
        start = time.time()
        D, I = gpu_index.search(xq, 5)
        gpu_time = time.time() - start
        
        print(f"    CPU: {cpu_time*1000:.1f}ms")
        print(f"    GPU: {gpu_time*1000:.1f}ms")
        print(f"    加速: {cpu_time/gpu_time:.1f}x")
    
    results.append(("Faiss", gpu_count > 0))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("Faiss", False))

# 4. YOLOv8
print("\n[4] YOLOv8")
try:
    from ultralytics import YOLO
    print("    ✅ 已安装")
    results.append(("YOLOv8", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("YOLOv8", False))

# 5. CLIP
print("\n[5] CLIP")
try:
    import clip
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"    正在加载模型（{device}）...")
    model, preprocess = clip.load("ViT-B/32", device=device)
    print("    ✅ 加载成功")
    results.append(("CLIP", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("CLIP", False))

# 6. FFmpeg
print("\n[6] FFmpeg")
try:
    import imageio_ffmpeg
    path = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"    路径: {path[:50]}...")
    results.append(("FFmpeg", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("FFmpeg", False))

# 7. Flask
print("\n[7] Flask")
try:
    import flask
    from flask_cors import CORS
    print("    ✅ 已安装")
    results.append(("Flask", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("Flask", False))

# 8. 数据库
print("\n[8] 数据库")
try:
    import pymysql
    import sqlalchemy
    print(f"    PyMySQL: {pymysql.__version__}")
    print(f"    SQLAlchemy: {sqlalchemy.__version__}")
    results.append(("数据库", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("数据库", False))

# 9. 其他
print("\n[9] 科学计算")
try:
    import numpy as np
    import pandas as pd
    import matplotlib
    print(f"    NumPy: {np.__version__}")
    print(f"    Pandas: {pd.__version__}")
    results.append(("科学计算", True))
except Exception as e:
    print(f"    ❌ {e}")
    results.append(("科学计算", False))

# 汇总
print("\n" + "="*60)
print("  汇总结果")
print("="*60)

for name, success in results:
    status = "✅" if success else "❌"
    print(f"{status} {name}")

passed = sum(1 for _, s in results if s)
total = len(results)

print("="*60)
print(f"总计: {passed}/{total} 通过")

if passed == total:
    print("\n🎉🎉🎉 完美！所有环境配置成功！🎉🎉🎉")
    print("\n✅ 可以开始开发视频检索系统了！")
    print("\n下一步：数据预处理模块开发")
elif passed >= 7:
    print(f"\n👍 很好！{passed}/{total} 通过")
    print("基本功能可用，可以开始开发！")
else:
    print(f"\n⚠️  还需修复 {total-passed} 项")

print("="*60 + "\n")