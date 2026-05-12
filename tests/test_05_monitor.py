import requests
from tests.conftest import BASE_URL


def test_get_sources(superuser_headers):
    resp = requests.get(f"{BASE_URL}/api/monitor/sources", headers=superuser_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert isinstance(body.get("sources"), list)


def test_get_status(superuser_headers):
    resp = requests.get(f"{BASE_URL}/api/monitor/status", headers=superuser_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True


def test_set_source_invalid(superuser_headers):
    # 不传 type 字段 → 400；传了不存在的 video 路径 → 500
    # 均属于"有错误处理"的合法失败
    resp = requests.post(
        f"{BASE_URL}/api/monitor/set_source",
        headers=superuser_headers,
        json={"source": "不存在的路径/fake_camera"},
    )
    assert resp.status_code in (400, 404, 500), (
        f"期望 400/404/500，实际: {resp.status_code}  body: {resp.text}"
    )


def test_stream_content_type(superuser_headers):
    resp = requests.get(
        f"{BASE_URL}/api/monitor/stream",
        headers=superuser_headers,
        stream=True,
        timeout=5,
    )
    try:
        assert resp.status_code == 200, resp.status_code
        ct = resp.headers.get("Content-Type", "")
        assert "multipart/x-mixed-replace" in ct, (
            f"Content-Type 不符合预期: {ct!r}"
        )
    finally:
        resp.close()


def test_stop_monitor(superuser_headers):
    resp = requests.post(f"{BASE_URL}/api/monitor/stop", headers=superuser_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True
