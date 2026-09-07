# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import io
import json

import pytest
from ansible.module_utils.six.moves.urllib.error import HTTPError

from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.config import AOConfig
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.direct_client import AODirectClient
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.exceptions import AOError, AuthenticationError


class FakeResponse:
    def __init__(self, data):
        self._data = json.dumps(data).encode("utf-8") if data is not None else b""

    def read(self):
        return self._data


def make_client(**config_kwargs):
    config = AOConfig(base_url="https://ao.example.com", **config_kwargs)
    return AODirectClient(config)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_password_login_sets_token(monkeypatch):
    client = make_client(username="admin", password="secret")

    def fake_open(method, url, **kwargs):
        assert "/api/v1/auth/login" in url
        body = json.loads(kwargs["data"])
        assert body == {"username": "admin", "password": "secret"}
        return FakeResponse({"access_token": "tok1", "expires_in": 900})

    client.session.open = fake_open
    client.ensure_auth()
    assert client._token == "tok1"
    assert client._token_expires_at > 0


def test_client_credentials_login_uses_form_encoding():
    client = make_client(client_id="cid", client_secret="csecret")

    def fake_open(method, url, **kwargs):
        assert "/api/v1/auth/token" in url
        assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
        assert "grant_type=client_credentials" in kwargs["data"]
        return FakeResponse({"access_token": "tok2", "expires_in": 3600})

    client.session.open = fake_open
    client.ensure_auth()
    assert client._token == "tok2"


def test_ensure_auth_reuses_valid_token():
    client = make_client(token="preset-token")
    calls = []
    client.session.open = lambda *a, **k: calls.append(1)
    client.ensure_auth()
    assert not calls  # no HTTP call needed; preset token has no expiry tracked


def test_ensure_auth_raises_without_any_credentials():
    client = make_client()
    with pytest.raises(AuthenticationError):
        client.ensure_auth()


def test_401_triggers_reauthentication_and_retries_once():
    client = make_client(username="admin", password="secret")
    client._token = "expired"
    client._token_expires_at = None

    def fake_open(method, url, **kwargs):
        if "/api/v1/auth/login" in url:
            return FakeResponse({"access_token": "freshtok", "expires_in": 900})
        if kwargs["headers"].get("Authorization") == "Bearer expired":
            raise HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b'{"detail": "expired"}'))
        assert kwargs["headers"]["Authorization"] == "Bearer freshtok"
        return FakeResponse({"resources": [], "next": None})

    client.session.open = fake_open
    result = client._raw_request("GET", "/api/v1/projects")
    assert result == {"resources": [], "next": None}
    assert client._token == "freshtok"


def test_non_401_http_error_raises_api_error():
    client = make_client(token="tok")

    def fake_open(method, url, **kwargs):
        raise HTTPError(url, 500, "Server Error", {}, io.BytesIO(b'{"detail": "boom"}'))

    client.session.open = fake_open
    with pytest.raises(AOError) as exc_info:
        client._raw_request("GET", "/api/v1/projects")
    assert exc_info.value.status_code == 500
    assert exc_info.value.retryable is True


# ---------------------------------------------------------------------------
# CRUD dispatch (project as the representative simple resource)
# ---------------------------------------------------------------------------


def test_execute_create_dispatches_to_endpoint_and_transforms_result():
    client = make_client(token="tok")
    seen = []

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        seen.append((method, path, body, query))
        assert method == "POST"
        assert path == "/api/v1/projects"
        return {"id": "abc-123", "name": body["name"], "description": body.get("description"), "labels": None, "created_at": "now", "updated_at": "now"}

    client._raw_request = fake_raw_request
    result = client.execute(operation="create", module_name="project", ansible_data_dict={"name": "demo", "description": "a demo project"})

    assert result["changed"] is True
    assert result["id"] == "abc-123"
    assert result["name"] == "demo"
    assert len(seen) == 1


def test_execute_find_falls_back_to_full_listing_when_filter_returns_nothing():
    client = make_client(token="tok")

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        if query and "name[eq]" in query:
            return {"resources": [], "next": None}
        return {"resources": [{"id": "abc-123", "name": "demo", "description": "x", "labels": None}], "next": None}

    client._raw_request = fake_raw_request
    result = client.execute(operation="find", module_name="project", ansible_data_dict={"name": "demo"})
    assert result["id"] == "abc-123"


def test_execute_find_raises_when_not_found():
    client = make_client(token="tok")
    client._raw_request = lambda *a, **k: {"resources": [], "next": None}
    with pytest.raises(ValueError):
        client.execute(operation="find", module_name="project", ansible_data_dict={"name": "missing"})


def test_execute_update_sends_patch_to_id_path():
    client = make_client(token="tok")
    seen = []

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        seen.append((method, path, body))
        assert method == "PATCH"
        assert path == "/api/v1/projects/abc-123"
        return {"id": "abc-123", "name": "demo", "description": body["description"], "labels": None}

    client._raw_request = fake_raw_request
    result = client.execute(operation="update", module_name="project", ansible_data_dict={"id": "abc-123", "name": "demo", "description": "updated"})
    assert result["description"] == "updated"
    assert result["changed"] is True


def test_execute_update_without_id_raises():
    client = make_client(token="tok")
    with pytest.raises(ValueError):
        client.execute(operation="update", module_name="project", ansible_data_dict={"name": "demo"})


def test_execute_delete_sends_delete_to_id_path():
    client = make_client(token="tok")
    seen = []

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        seen.append((method, path))
        return None

    client._raw_request = fake_raw_request
    result = client.execute(operation="delete", module_name="project", ansible_data_dict={"id": "abc-123", "name": "demo"})
    assert result == {"changed": True, "deleted": True}
    assert seen == [("DELETE", "/api/v1/projects/abc-123")]


# ---------------------------------------------------------------------------
# Pagination and name/id resolution
# ---------------------------------------------------------------------------


def test_list_all_follows_cursor():
    client = make_client(token="tok")
    pages = [
        {"resources": [{"id": "1"}], "next": "cursor2"},
        {"resources": [{"id": "2"}], "next": None},
    ]

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        return pages.pop(0)

    client._raw_request = fake_raw_request
    resources = client.list_all("/api/v1/projects")
    assert [r["id"] for r in resources] == ["1", "2"]


def test_resolve_id_returns_uuid_unchanged():
    client = make_client(token="tok")
    uuid_value = "123e4567-e89b-12d3-a456-426614174000"
    assert client.resolve_id("/api/v1/projects", uuid_value) == uuid_value


def test_resolve_id_looks_up_by_name_and_caches():
    client = make_client(token="tok")
    calls = []

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        calls.append((method, path, query))
        return {"resources": [{"id": "resolved-id", "name": "myproj"}], "next": None}

    client._raw_request = fake_raw_request
    first = client.resolve_id("/api/v1/projects", "myproj")
    second = client.resolve_id("/api/v1/projects", "myproj")
    assert first == "resolved-id"
    assert second == "resolved-id"
    # Second call should hit the cache, not issue another HTTP request.
    assert len(calls) == 1


def test_resolve_id_required_raises_when_missing():
    client = make_client(token="tok")
    with pytest.raises(AOError):
        client.resolve_id("/api/v1/projects", None, required=True)


def test_resolve_id_optional_returns_none_when_missing():
    client = make_client(token="tok")
    assert client.resolve_id("/api/v1/projects", None, required=False) is None
