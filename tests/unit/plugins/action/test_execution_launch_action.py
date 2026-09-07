# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
from ansible.errors import AnsibleError

from ansible_collections.infra.automation_orchestrator.plugins.action.execution_launch import ActionModule
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.config import AOConfig
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.direct_client import AODirectClient

WORKFLOW_UUID = "33333333-3333-3333-3333-333333333333"
PROJECT_UUID = "11111111-1111-1111-1111-111111111111"


def make_client():
    return AODirectClient(AOConfig(base_url="https://ao.example.com", token="tok"))


def test_resolve_workflow_id_passes_through_uuid():
    client = make_client()
    client._raw_request = lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call the API for a UUID"))
    assert ActionModule._resolve_workflow_id(None, client, WORKFLOW_UUID, None) == WORKFLOW_UUID


def test_resolve_workflow_id_looks_up_by_name_scoped_to_project():
    client = make_client()

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        if path == "/api/v1/projects" and query.get("name[eq]") == "my-project":
            return {"resources": [{"id": PROJECT_UUID, "name": "my-project"}], "next": None}
        if path == "/api/v1/workflows" and query.get("project_id[eq]") == PROJECT_UUID and query.get("name[eq]") == "hello":
            return {"resources": [{"id": WORKFLOW_UUID, "name": "hello"}], "next": None}
        raise AssertionError(f"unexpected: {method} {path} {query}")

    client._raw_request = fake_raw_request
    assert ActionModule._resolve_workflow_id(None, client, "hello", "my-project") == WORKFLOW_UUID


def test_resolve_workflow_id_falls_back_to_full_listing():
    client = make_client()

    def fake_raw_request(method, path, body=None, form=None, query=None, authenticate=True, _retry=True):
        if path == "/api/v1/workflows" and "name[eq]" in query:
            return {"resources": [], "next": None}
        if path == "/api/v1/workflows":
            return {"resources": [{"id": WORKFLOW_UUID, "name": "hello"}], "next": None}
        raise AssertionError(f"unexpected: {method} {path} {query}")

    client._raw_request = fake_raw_request
    assert ActionModule._resolve_workflow_id(None, client, "hello", None) == WORKFLOW_UUID


def test_resolve_workflow_id_raises_when_not_found():
    client = make_client()
    client._raw_request = lambda *a, **k: {"resources": [], "next": None}
    with pytest.raises(AnsibleError):
        ActionModule._resolve_workflow_id(None, client, "missing", None)


def test_resolve_workflow_id_raises_on_ambiguous_match():
    client = make_client()
    client._raw_request = lambda *a, **k: {
        "resources": [{"id": "aaaa", "name": "hello"}, {"id": "bbbb", "name": "hello"}],
        "next": None,
    }
    with pytest.raises(AnsibleError):
        ActionModule._resolve_workflow_id(None, client, "hello", None)
