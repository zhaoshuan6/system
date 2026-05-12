import requests
import pytest
from tests.conftest import BASE_URL


# ----------------------------------------------------------------
#  module-level setup: 各跑一次文本检索，确保历史表里有两个不同用户的记录
# ----------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def setup_history(superuser_headers, admin_headers):
    for headers in (superuser_headers, admin_headers):
        requests.post(
            f"{BASE_URL}/api/search/text",
            headers=headers,
            json={"query": "历史记录测试", "top_k": 3},
            timeout=30,
        )


# ----------------------------------------------------------------
#  测试用例
# ----------------------------------------------------------------

def test_superuser_can_see_history(superuser_headers):
    resp = requests.get(f"{BASE_URL}/api/history", headers=superuser_headers)
    assert resp.status_code == 200, resp.text
    records = resp.json().get("records", [])
    assert len(records) > 0, "历史记录为空"


def test_admin_can_see_own_history(admin_headers):
    resp = requests.get(f"{BASE_URL}/api/history", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True


def test_superuser_sees_all_users_history(superuser_headers):
    resp = requests.get(f"{BASE_URL}/api/history", headers=superuser_headers)
    assert resp.status_code == 200
    records = resp.json().get("records", [])
    usernames = {r["username"] for r in records}
    assert len(usernames) > 1, (
        f"超管应能看到多个用户的记录，实际只有: {usernames}"
    )


def test_admin_sees_only_own_history(admin_headers):
    resp = requests.get(f"{BASE_URL}/api/history", headers=admin_headers)
    assert resp.status_code == 200
    records = resp.json().get("records", [])
    for r in records:
        assert r["username"] == "test_admin", (
            f"admin 看到了他人记录: {r['username']}"
        )


def test_history_filter_by_type(superuser_headers):
    resp = requests.get(
        f"{BASE_URL}/api/history",
        headers=superuser_headers,
        params={"type": "text"},
    )
    assert resp.status_code == 200, resp.text
    records = resp.json().get("records", [])
    for r in records:
        assert r["search_type"] == "text", (
            f"过滤 type=text 后出现非 text 记录: {r['search_type']}"
        )


def test_delete_history_record(admin_headers):
    # 取 admin 自己的第一条记录
    resp = requests.get(f"{BASE_URL}/api/history", headers=admin_headers)
    assert resp.status_code == 200
    records = resp.json().get("records", [])
    assert len(records) > 0, "admin 历史为空，无法测试删除"

    record_id = records[0]["id"]

    # 删除
    del_resp = requests.delete(
        f"{BASE_URL}/api/history/{record_id}",
        headers=admin_headers,
    )
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json().get("success") is True

    # 确认已不存在
    resp2 = requests.get(f"{BASE_URL}/api/history", headers=admin_headers)
    ids_after = {r["id"] for r in resp2.json().get("records", [])}
    assert record_id not in ids_after, f"record_id={record_id} 删除后仍存在"
