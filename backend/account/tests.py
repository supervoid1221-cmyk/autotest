from pathlib import Path

from django.contrib.auth.models import User

from .models import Profile


def test_login(user, api_client):
    resp = api_client.post(
        "/api/account/profile/login/",
        {
            "username": "test_user",
            "password": "test_user_pass",
        },
        format="json",
    )

    assert resp.status_code == 200, resp.status_code


def test_login_ignores_stale_token(user, api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Token stale-token-from-browser")

    resp = api_client.post(
        "/api/account/profile/login/",
        {
            "username": "test_user",
            "password": "test_user_pass",
        },
        format="json",
    )

    assert resp.status_code == 200, resp.data


def test_reset_password(user: User, user_api_client):
    resp = user_api_client.post(
        "/api/account/profile/reset_password/",
        {
            "new_password": "1234567",
            "confirm_password": "1234567",
        },
        format="json",
    )

    assert resp.status_code == 204, resp.status_code

    # 通过数据库方式验证新密码
    user.refresh_from_db()  # 加载新数据内容
    assert user.check_password("1234567")

    # 通过接口的方式验证新密码
    user_api_client.logout()  # 退出登录
    resp = user_api_client.post(
        "/api/account/profile/login/",
        {  # 尝试重新登录
            "username": "test_user",
            "password": "1234567",
        },
        format="json",
    )

    assert resp.status_code == 200, resp.status_code


def test_api_401(api_client):
    resp = api_client.get("/api/account/profile/profile/")

    assert resp.status_code == 401, resp.status_code


def test_get_profile(user_api_client, user):
    resp = user_api_client.get("/api/account/profile/profile/")

    assert resp.status_code == 200, resp.status_code

    assert resp.data["user"] == user.id


