#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Week 3 API 测试脚本
测试所有接口是否正常工作

用法：
  1. 先启动后端：python run.py
  2. 新开终端运行：python tests/test_api.py
"""

import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://localhost:5000"

def ok(msg):  print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def info(msg): print(f"  ℹ️  {msg}")


def test_health():
    print("\n[1/6] 健康检查")
    print("-" * 50)
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        data = r.json()
        if data.get("status") == "ok":
            ok(f"服务正常: {data['message']}")
            return True
        fail(f"异常响应: {data}")
        return False
    except requests.ConnectionError:
        fail("无法连接到后端，请先运行: python run.py")
        return False
    except Exception as e:
        fail(f"请求失败: {e}")
        return False


def test_get_sources():
    print("\n[2/6] 获取视频源列表")
    print("-" * 50)
    try:
        r = requests.get(f"{BASE_URL}/api/monitor/sources", timeout=10)
        data = r.json()
        sources = data.get("sources", [])
        ok(f"获取视频源成功，共 {len(sources)} 个")
        for s in sources:
            info(f"  {s['type']}: {s['name']}")
        return True
    except Exception as e:
        fail(f"失败: {e}")
        return False


def test_monitor_status():
    print("\n[3/6] 监控状态查询")
    print("-" * 50)
    try:
        r = requests.get(f"{BASE_URL}/api/monitor/status", timeout=5)
        data = r.json()
        ok(f"监控状态: active={data.get('is_active')}, type={data.get('type')}")
        return True
    except Exception as e:
        fail(f"失败: {e}")
        return False


def test_list_videos():
    print("\n[4/6] 获取视频列表")
    print("-" * 50)
    try:
        r = requests.get(f"{BASE_URL}/api/data/videos", timeout=5)
        data = r.json()
        videos = data.get("videos", [])
        ok(f"获取视频列表成功，共 {len(videos)} 个视频")
        for v in videos:
            info(f"  video_id={v['video_id']} frames={v['frame_count']} persons={v['object_count']} loc={v['camera_location']}")
        return True
    except Exception as e:
        fail(f"失败: {e}")
        return False


def test_text_search():
    print("\n[5/6] 文字搜图测试")
    print("-" * 50)
    try:
        payload = {"query": "a person walking", "top_k": 5}
        r = requests.post(f"{BASE_URL}/api/search/text", json=payload, timeout=30)
        data = r.json()
        if data.get("success"):
            results = data.get("results", [])
            ok(f"文字搜图成功，返回 {len(results)} 个视频")
            for res in results[:2]:
                info(f"  video_id={res['video_id']} score={res['max_score']} loc={res['camera_location']}")
                info(f"  出现次数: {len(res['appearances'])}")
        else:
            fail(f"搜索失败: {data.get('error')}")
            return False
        return True
    except Exception as e:
        fail(f"失败: {e}")
        return False


def test_image_search():
    print("\n[6/6] 以图搜图测试")
    print("-" * 50)

    # 找一张关键帧图片来测试
    frame_dir = Path("data/processed")
    images = list(frame_dir.rglob("*.jpg"))

    if not images:
        info("未找到测试图片，跳过以图搜图测试")
        info("（请先运行 test_mot17.py 生成关键帧）")
        return True

    test_image = images[0]
    info(f"使用测试图片: {test_image.name}")

    try:
        with open(test_image, "rb") as f:
            files = {"image": (test_image.name, f, "image/jpeg")}
            data  = {"top_k": 5}
            r = requests.post(f"{BASE_URL}/api/search/image", files=files, data=data, timeout=30)

        result = r.json()
        if result.get("success"):
            results = result.get("results", [])
            ok(f"以图搜图成功，返回 {len(results)} 个视频")
            ok(f"是否检测到人物并裁剪: {result.get('detected_person')}")
            for res in results[:2]:
                info(f"  video_id={res['video_id']} score={res['max_score']}")
        else:
            fail(f"搜索失败: {result.get('error')}")
            return False
        return True
    except Exception as e:
        fail(f"失败: {e}")
        return False


def main():
    print("=" * 55)
    print("  Week 3 API 测试")
    print("=" * 55)
    print(f"  目标地址: {BASE_URL}")

    tests = [
        ("健康检查",     test_health),
        ("视频源列表",   test_get_sources),
        ("监控状态",     test_monitor_status),
        ("视频列表",     test_list_videos),
        ("文字搜图",     test_text_search),
        ("以图搜图",     test_image_search),
    ]

    results = []
    for name, fn in tests:
        ok_flag = fn()
        results.append((name, ok_flag))
        if name == "健康检查" and not ok_flag:
            print("\n⛔ 后端未启动，终止测试")
            break

    print("\n" + "=" * 55)
    print("  测试结果汇总")
    print("=" * 55)
    for name, flag in results:
        print(f"  {'✅' if flag else '❌'} {name}")

    passed = sum(1 for _, f in results if f)
    print(f"\n  {passed}/{len(results)} 通过")

    if passed == len(tests):
        print("\n🎉 Week 3 全部通过！可以开始 Week 4 前端开发")
    print("=" * 55)


if __name__ == "__main__":
    main()
