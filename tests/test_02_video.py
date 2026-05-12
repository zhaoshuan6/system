import time
import requests
import pytest
from pathlib import Path
from tests.conftest import BASE_URL

TEST_DATA_DIR   = Path(__file__).parent / "test_data"
RESULTS_DIR     = Path(__file__).parent / "results"
VIDEO_ID_FILE   = RESULTS_DIR / "test_video_id.txt"
TEST_VIDEO_PATH = TEST_DATA_DIR / "test_video.mp4"


def test_upload_video_success(superuser_headers):
    with open(TEST_VIDEO_PATH, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/data/upload",
            headers=superuser_headers,
            files={"video": ("test_video.mp4", f, "video/mp4")},
            timeout=120,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    video_id = body.get("video_id")
    assert video_id is not None

    RESULTS_DIR.mkdir(exist_ok=True)
    VIDEO_ID_FILE.write_text(str(video_id))


def test_upload_invalid_format(superuser_headers):
    resp = requests.post(
        f"{BASE_URL}/api/data/upload",
        headers=superuser_headers,
        files={"video": ("test.txt", b"hello", "text/plain")},
        timeout=30,
    )
    assert resp.status_code == 400


# 上传路由不要求认证（data 蓝图无 JWT 装饰器），无 token 同样可以上传成功
def test_upload_without_auth():
    with open(TEST_VIDEO_PATH, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/data/upload",
            files={"video": ("test_video.mp4", f, "video/mp4")},
            timeout=120,
        )
    # 该路由无鉴权保护，预期返回 200（而非 401）
    assert resp.status_code == 200, resp.text


def test_video_appears_in_list(superuser_headers):
    # 上传处理虽为同步，额外等待确保数据库写入完成
    time.sleep(15)

    assert VIDEO_ID_FILE.exists(), "请先运行 test_upload_video_success"
    video_id = int(VIDEO_ID_FILE.read_text().strip())

    resp = requests.get(f"{BASE_URL}/api/data/videos", headers=superuser_headers)
    assert resp.status_code == 200
    videos = resp.json().get("videos", [])
    assert len(videos) > 0

    ids = [v["video_id"] for v in videos]
    assert video_id in ids, f"video_id={video_id} 未出现在列表 {ids} 中"


def test_get_video_detail(superuser_headers):
    assert VIDEO_ID_FILE.exists(), "请先运行 test_upload_video_success"
    video_id = int(VIDEO_ID_FILE.read_text().strip())

    resp = requests.get(
        f"{BASE_URL}/api/data/videos/{video_id}",
        headers=superuser_headers,
    )
    assert resp.status_code == 200
    video = resp.json().get("video", {})
    for field in ("video_id", "file_path", "duration"):
        assert field in video, f"响应中缺少字段: {field}"
