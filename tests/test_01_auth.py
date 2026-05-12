import requests
import pytest
from tests.conftest import BASE_URL


def test_login_admin_success():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "test_admin", "password": "Admin1234!"})
    assert resp.status_code == 200
    token = resp.json().get("token")
    assert token and len(token) > 0


def test_login_superuser_success():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "superuser", "password": "Test1234!"})
    assert resp.status_code == 200
    assert resp.json().get("token")


def test_login_wrong_password():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "test_admin", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_missing_username():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"password": "Admin1234!"})
    assert resp.status_code == 400


def test_access_without_token():
    resp = requests.get(f"{BASE_URL}/api/auth/me")
    assert resp.status_code == 401


def test_access_with_valid_token(admin_headers):
    resp = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == "test_admin"


def test_admin_cannot_list_users(admin_headers):
    resp = requests.get(f"{BASE_URL}/api/auth/users", headers=admin_headers)
    assert resp.status_code == 403


def test_superuser_can_list_users(superuser_headers):
    resp = requests.get(f"{BASE_URL}/api/auth/users", headers=superuser_headers)
    assert resp.status_code == 200
    users = resp.json().get("users", [])
    usernames = [u["username"] for u in users]
    assert "test_admin" in usernames


def test_health_check():
    resp = requests.get(f"{BASE_URL}/api/health")
    assert resp.status_code == 200
