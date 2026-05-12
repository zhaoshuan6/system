import json
import time
import statistics
import requests
from pathlib import Path
from tests.conftest import BASE_URL, get_token

RESULTS_DIR      = Path(__file__).parent / "results"
TEST_DATA_DIR    = Path(__file__).parent / "test_data"
TEST_PERSON_PATH = TEST_DATA_DIR / "test_person.jpg"
TEST_VIDEO_PATH  = TEST_DATA_DIR / "test_video.mp4"

token   = get_token("superuser", "Test1234!")
headers = {"Authorization": f"Bearer {token}"}


def _write_json(filename: str, data: dict):
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / filename).write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


def test_text_search_performance():
    durations = []
    success   = 0
    total     = 30

    for _ in range(total):
        t0 = time.perf_counter()
        resp = requests.post(
            f"{BASE_URL}/api/search/text",
            headers=headers,
            json={"query": "人物", "top_k": 5},
            timeout=10,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        durations.append(elapsed_ms)
        if resp.status_code == 200:
            success += 1
        time.sleep(0.5)

    avg    = statistics.mean(durations)
    result = {
        "avg_ms":       round(avg, 2),
        "max_ms":       round(max(durations), 2),
        "min_ms":       round(min(durations), 2),
        "median_ms":    round(statistics.median(durations), 2),
        "success_count": success,
        "total":        total,
    }
    _write_json("perf_text_search.json", result)

    assert avg < 3000, (
        f"文本检索平均响应时间 {avg:.1f}ms 超过 3000ms 阈值\n结果: {result}"
    )


def test_image_search_performance():
    durations = []
    success   = 0
    total     = 20

    for _ in range(total):
        with open(TEST_PERSON_PATH, "rb") as f:
            t0 = time.perf_counter()
            resp = requests.post(
                f"{BASE_URL}/api/search/image",
                headers=headers,
                files={"image": ("test_person.jpg", f, "image/jpeg")},
                timeout=15,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        durations.append(elapsed_ms)
        if resp.status_code == 200:
            success += 1
        time.sleep(0.5)

    avg    = statistics.mean(durations)
    result = {
        "avg_ms":        round(avg, 2),
        "max_ms":        round(max(durations), 2),
        "min_ms":        round(min(durations), 2),
        "median_ms":     round(statistics.median(durations), 2),
        "success_count": success,
        "total":         total,
    }
    _write_json("perf_image_search.json", result)

    assert avg < 5000, (
        f"图像检索平均响应时间 {avg:.1f}ms 超过 5000ms 阈值\n结果: {result}"
    )


def test_video_process_performance():
    file_size_mb = round(TEST_VIDEO_PATH.stat().st_size / (1024 * 1024), 2)

    with open(TEST_VIDEO_PATH, "rb") as f:
        t0 = time.perf_counter()
        resp = requests.post(
            f"{BASE_URL}/api/data/upload",
            headers=headers,
            files={"video": ("test_video.mp4", f, "video/mp4")},
            timeout=300,
        )
    process_time_ms = round((time.perf_counter() - t0) * 1000, 2)

    assert resp.status_code == 200, f"上传失败: {resp.text}"

    result = {
        "process_time_ms": process_time_ms,
        "file_size_mb":    file_size_mb,
    }
    _write_json("perf_video_process.json", result)
