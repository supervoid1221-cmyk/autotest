"""
@Filename:   /conftest
@Author:
@Time:
@Describe:    ...
"""

import pytest
from django.contrib.auth.models import User
from django.test.client import Client
from rest_framework.test import APIClient


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture()
def user(_django_db_helper):
    new_user = User.objects.create_user(
        username="test_user",
        email="test_user@qq.com",
        password="test_user_pass",
    )

    return new_user


@pytest.fixture()
def user_client(client: Client, user):
    client.force_login(user)
    return client


@pytest.fixture()
def user_api_client(api_client: APIClient, user):
    api_client.force_authenticate(user)
    return api_client
