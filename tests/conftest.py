import os
import pytest
import requests

# 绕过代理，避免 http_proxy 环境变量拦截 localhost 请求
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

BASE_URL = "http://localhost:5000"

SUPERUSER = {"username": "superuser", "password": "Test1234!"}
ADMIN     = {"username": "test_admin", "password": "Admin1234!"}


def get_token(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def superuser_token():
    return get_token(SUPERUSER["username"], SUPERUSER["password"])


@pytest.fixture(scope="session")
def admin_token():
    return get_token(ADMIN["username"], ADMIN["password"])


@pytest.fixture(scope="session")
def superuser_headers(superuser_token):
    return auth_headers(superuser_token)


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return auth_headers(admin_token)
