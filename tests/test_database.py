#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Week 2 测试脚本
测试内容：
  1. MySQL 连接是否正常
  2. 数据表是否创建成功
  3. 将 test_mot17.py 生成的 pickle 写入数据库
  4. 从数据库读取数据验证
  5. FAISS 索引构建验证

用法：
    python tests/test_database.py
"""

import os
import sys
from pathlib import Path

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_mysql_connection():
    """测试 MySQL 连接"""
    print("\n[1/5] 测试 MySQL 连接")
    print("-" * 50)
    try:
        import pymysql
        from config import MYSQL_CONFIG
        conn = pymysql.connect(
            host=MYSQL_CONFIG["host"],
            port=MYSQL_CONFIG["port"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
        )
        conn.close()
        print("✅ MySQL 连接成功")
        return True
    except Exception as e:
        print(f"❌ MySQL 连接失败: {e}")
        print("\n请检查：")
        print("  1. MySQL 服务是否已启动")
        print("  2. config.py 中的密码是否正确")
        return False


def test_create_tables():
    """测试建表"""
    print("\n[2/5] 测试建表")
    print("-" * 50)
    try:
        from backend.database.db import get_db_engine
        engine = get_db_engine()
        print("✅ 数据库和表创建成功")

        # 显示创建的表
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"   已创建的表: {tables}")
        return True
    except Exception as e:
        print(f"❌ 建表失败: {e}")
        return False


def test_ingest():
    """测试数据入库"""
    print("\n[3/5] 测试数据入库")
    print("-" * 50)

    # 查找 test_mot17.py 生成的 pickle 文件
    processed_dir = project_root / "data" / "processed"
    pkl_files = list(processed_dir.rglob("*_processed.pkl"))

    if not pkl_files:
        print("⚠️  未找到 pickle 文件，请先运行 test_mot17.py")
        print(f"   查找路径: {processed_dir}")
        return False

    pkl_file = pkl_files[0]
    print(f"   使用文件: {pkl_file.name}")

    try:
        from backend.database.ingest import ingest
        video_id = ingest(
            pickle_path=str(pkl_file),
            video_path=str(project_root / "data" / "videos" / f"{pkl_file.stem.replace('_processed', '')}.mp4"),
            camera_id=1,
            camera_location="测试摄像头-1号位",
        )
        print(f"✅ 数据入库成功，video_id={video_id}")
        return True
    except Exception as e:
        print(f"❌ 数据入库失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_db():
    """测试从数据库查询"""
    print("\n[4/5] 测试数据库查询")
    print("-" * 50)
    try:
        from backend.database.db import get_session
        from backend.database.models import VideoMetadata, KeyFrame, DetectedObject, Trajectory

        session = get_session()

        videos   = session.query(VideoMetadata).all()
        frames   = session.query(KeyFrame).all()
        objects  = session.query(DetectedObject).all()
        trajs    = session.query(Trajectory).all()

        print(f"✅ 数据库查询成功")
        print(f"   视频数:   {len(videos)}")
        print(f"   关键帧数: {len(frames)}")
        print(f"   检测目标: {len(objects)}")
        print(f"   轨迹记录: {len(trajs)}")

        if objects:
            feat = objects[0].get_feature()
            print(f"   特征维度验证: {feat.shape} (应为 (512,))")

        session.close()
        return True
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_faiss_index():
    """测试 FAISS 索引"""
    print("\n[5/5] 测试 FAISS 索引")
    print("-" * 50)
    try:
        from backend.database.db import get_session
        from backend.models.feature_index import FeatureIndex
        from config import FAISS_CONFIG
        import numpy as np

        index = FeatureIndex(
            dim=FAISS_CONFIG["dim"],
            index_path=FAISS_CONFIG["index_path"],
        )

        # 尝试从文件加载
        if index.load():
            print(f"✅ 从文件加载索引成功，共 {index.total} 条向量")
        else:
            # 从数据库重建
            session = get_session()
            count = index.build_from_db(session)
            session.close()
            if count > 0:
                index.save()
                print(f"✅ 从数据库构建索引成功，共 {count} 条向量")
            else:
                print("⚠️  索引为空（数据库无数据）")
                return False

        # 测试检索
        query = np.random.randn(512).astype(np.float32)
        results = index.search(query, top_k=3)
        print(f"✅ FAISS 检索测试通过，返回 {len(results)} 条结果")
        if results:
            print(f"   第1条结果: video_id={results[0]['video_id']} score={results[0]['score']:.4f}")

        return True
    except Exception as e:
        print(f"❌ FAISS 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("  Week 2 数据库测试")
    print("=" * 60)

    tests = [
        ("MySQL连接",   test_mysql_connection),
        ("建表",        test_create_tables),
        ("数据入库",    test_ingest),
        ("数据库查询",  test_query_db),
        ("FAISS索引",   test_faiss_index),
    ]

    results = []
    for name, fn in tests:
        ok = fn()
        results.append((name, ok))
        if not ok and name in ("MySQL连接", "建表"):
            print("\n⛔ 基础连接失败，终止测试")
            break

    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n  {passed}/{len(results)} 通过")

    if passed == len(tests):
        print("\n🎉 Week 2 全部通过！可以开始 Week 3 API 开发")
    print("=" * 60)


if __name__ == "__main__":
    main()
