# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.config import AOConfig
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.direct_client import AODirectClient

CRED = "22222222-2222-2222-2222-222222222222"


def make_client():
    return AODirectClient(AOConfig(base_url="https://ao.example.com", token="tok"))


def test_resolve_workflow_definition_converts_name_to_id():
    client = make_client()

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        if method == "GET" and path == "/api/v1/credentials" and query and query.get("name[eq]") == "my-cred":
            return {"resources": [{"id": CRED, "name": "my-cred"}], "next": None}
        raise AssertionError(f"unexpected: {method} {path} {query}")

    client._raw_request = fake_raw_request
    definition = {"nodes": [{"id": "n1", "credential": "my-cred"}]}
    resolved = client.resolve_workflow_definition(definition)
    assert resolved["nodes"][0]["credential_id"] == CRED
    assert "credential" not in resolved["nodes"][0]


def test_resolve_workflow_definition_leaves_existing_uuid_alone():
    client = make_client()
    client._raw_request = lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call the API for an already-resolved UUID"))
    definition = {"credential_id": CRED}
    resolved = client.resolve_workflow_definition(definition)
    assert resolved["credential_id"] == CRED


def test_names_workflow_definition_converts_id_back_to_name():
    client = make_client()

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        if method == "GET" and path == f"/api/v1/credentials/{CRED}":
            return {"id": CRED, "name": "my-cred"}
        raise AssertionError(f"unexpected: {method} {path}")

    client._raw_request = fake_raw_request
    definition = {"nodes": [{"id": "n1", "credential_id": CRED}]}
    named = client.names_workflow_definition(definition)
    assert named["nodes"][0]["credential_id"] == "my-cred"


def test_resolve_workflow_definition_empty_is_noop():
    client = make_client()
    assert client.resolve_workflow_definition(None) is None
    assert client.resolve_workflow_definition({}) == {}
