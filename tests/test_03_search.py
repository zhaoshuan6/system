import io
import requests
import pytest
from pathlib import Path
from PIL import Image
from tests.conftest import BASE_URL

TEST_DATA_DIR    = Path(__file__).parent / "test_data"
RESULTS_DIR      = Path(__file__).parent / "results"
VIDEO_ID_FILE    = RESULTS_DIR / "test_video_id.txt"
TEST_PERSON_PATH = TEST_DATA_DIR / "test_person.jpg"


# ----------------------------------------------------------------
#  POST /api/search/text
# ----------------------------------------------------------------

def test_text_search_success(superuser_headers):
    resp = requests.post(
        f"{BASE_URL}/api/search/text",
        headers=superuser_headers,
        json={"query": "人物", "top_k": 5},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert isinstance(body.get("results"), list)


def test_text_search_result_format(superuser_headers):
    resp = requests.post(
        f"{BASE_URL}/api/search/text",
        headers=superuser_headers,
        json={"query": "人物", "top_k": 5},
    )
    assert resp.status_code == 200
    results = resp.json().get("results", [])
    assert len(results) > 0, "搜索结果为空，无法验证格式"

    first = results[0]
    assert "video_id" in first
    # frame_path 和 score 在 appearances 列表中
    assert "appearances" in first and len(first["appearances"]) > 0
    appearance = first["appearances"][0]
    assert "frame_path" in appearance
    assert "score" in appearance
    score = appearance["score"]
    assert isinstance(score, float), f"score 不是浮点数: {score!r}"
    assert 0.0 <= score <= 1.0, f"score 不在 [0, 1] 范围内: {score}"


def test_text_search_empty_query(superuser_headers):
    resp = requests.post(
        f"{BASE_URL}/api/search/text",
        headers=superuser_headers,
        json={"query": "", "top_k": 5},
    )
    assert resp.status_code == 400


# ----------------------------------------------------------------
#  POST /api/search/image
# ----------------------------------------------------------------

def test_image_search_with_person(superuser_headers):
    with open(TEST_PERSON_PATH, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/search/image",
            headers=superuser_headers,
            files={"image": ("test_person.jpg", f, "image/jpeg")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert isinstance(body.get("results"), list)


def test_image_search_result_format(superuser_headers):
    with open(TEST_PERSON_PATH, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/search/image",
            headers=superuser_headers,
            files={"image": ("test_person.jpg", f, "image/jpeg")},
        )
    assert resp.status_code == 200
    results = resp.json().get("results", [])
    assert len(results) > 0, "搜索结果为空，无法验证格式"

    first = results[0]
    assert "video_id" in first
    assert "appearances" in first and len(first["appearances"]) > 0
    appearance = first["appearances"][0]
    assert "frame_path" in appearance
    assert "score" in appearance


def test_image_search_no_person(superuser_headers):
    # 生成纯白图片
    white_img = Image.new("RGB", (100, 100), (255, 255, 255))
    buf = io.BytesIO()
    white_img.save(buf, format="JPEG")
    buf.seek(0)

    resp = requests.post(
        f"{BASE_URL}/api/search/image",
        headers=superuser_headers,
        files={"image": ("white.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # 接口对无人物图片的三种合法响应：
    # 1. 有 degraded/warning 字段（降级提示）
    # 2. results 为空列表
    # 3. detected_person == False（YOLO未检测到人，用原图特征搜索）
    has_degraded = body.get("degraded") is not None or body.get("warning") is not None
    results_empty = body.get("results") == []
    no_person_detected = body.get("detected_person") is False

    assert has_degraded or results_empty or no_person_detected, (
        f"纯白图搜索响应不符合预期: {body}"
    )
