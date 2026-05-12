import requests
import pytest
from pathlib import Path
from tests.conftest import BASE_URL

TEST_DATA_DIR    = Path(__file__).parent / "test_data"
TEST_PERSON_PATH = TEST_DATA_DIR / "test_person.jpg"

# 轨迹接口接受图片文件（multipart），threshold/top_k 通过 form 字段传递
_FORM = {"top_k": "20", "threshold": "0.2"}


def _post_trajectory(headers):
    with open(TEST_PERSON_PATH, "rb") as f:
        return requests.post(
            f"{BASE_URL}/api/search/trajectory",
            headers=headers,
            files={"image": ("test_person.jpg", f, "image/jpeg")},
            data=_FORM,
            timeout=60,
        )


def test_trajectory_success(superuser_headers):
    resp = _post_trajectory(superuser_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True


def test_trajectory_response_format(superuser_headers):
    resp = _post_trajectory(superuser_headers)
    assert resp.status_code == 200
    body = resp.json()

    trajectory = body.get("trajectory")
    assert isinstance(trajectory, list), "trajectory 字段应为列表"

    if trajectory:
        first = trajectory[0]
        assert "video_id"   in first, "缺少 video_id 字段"
        assert "frame_path" in first, "缺少 frame_path 字段"
        # 时间戳字段为 frame_time（API 实际字段名）
        assert "frame_time" in first, "缺少 frame_time 字段"


def test_trajectory_sorted(superuser_headers):
    resp = _post_trajectory(superuser_headers)
    assert resp.status_code == 200
    trajectory = resp.json().get("trajectory", [])

    if len(trajectory) < 2:
        pytest.skip("结果不足 2 条，跳过排序断言")

    # API 按 (video_id, frame_time) 升序排列
    keys = [(t["video_id"], t["frame_time"]) for t in trajectory]
    assert keys == sorted(keys), (
        f"trajectory 未按 (video_id, frame_time) 升序排列\n实际顺序: {keys}"
    )


def test_trajectory_no_duplicate_frames(superuser_headers):
    resp = _post_trajectory(superuser_headers)
    assert resp.status_code == 200
    trajectory = resp.json().get("trajectory", [])

    combos = [(t["video_id"], t["frame_path"]) for t in trajectory]
    assert len(combos) == len(set(combos)), (
        f"存在重复的 (video_id, frame_path) 组合: "
        f"{[c for c in combos if combos.count(c) > 1]}"
    )
