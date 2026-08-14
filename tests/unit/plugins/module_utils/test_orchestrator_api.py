# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import (
    OrchestratorAPIModule,
    OrchestratorModule,
)


@pytest.fixture
def module_factory():
    def _factory(**extra_params):
        params = {
            "orchestrator_host": "https://orchestrator.example.com",
            "orchestrator_token": "test-token",
            "validate_certs": True,
            "request_timeout": 30,
        }
        params.update(extra_params)
        with patch.object(OrchestratorModule, "load_config_files"):
            with patch(
                "ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api.getaddrinfo"
            ):
                return OrchestratorAPIModule(argument_spec={}, direct_params=params)

    return _factory


def test_is_uuid(module_factory):
    module = module_factory()
    assert module.is_uuid("c5da59c2-ca69-44e1-bf96-1777606aab5c")
    assert not module.is_uuid("not-a-uuid")


def test_fields_could_be_same_encrypted():
    assert OrchestratorAPIModule.fields_could_be_same("$encrypted$", "secret")
    assert OrchestratorAPIModule.fields_could_be_same("abc", "abc")
    assert not OrchestratorAPIModule.fields_could_be_same("abc", "def")


def test_build_url(module_factory):
    module = module_factory()
    url = module.build_url("projects")
    assert url.path == "/api/v1/projects"


def test_get_all_endpoint_follows_cursors(module_factory):
    module = module_factory()

    first_page = {
        "resources": [{"id": "1", "name": "one"}],
        "next": "cursor-2",
        "prev": None,
        "total": None,
    }
    second_page = {
        "resources": [{"id": "2", "name": "two"}],
        "next": None,
        "prev": "cursor-1",
        "total": None,
    }

    with patch.object(
        module,
        "get_endpoint",
        side_effect=[
            {"status_code": 200, "json": first_page},
            {"status_code": 200, "json": second_page},
        ],
    ) as get_endpoint:
        response = module.get_all_endpoint("projects")

    assert len(response["json"]["resources"]) == 2
    assert get_endpoint.call_count == 2
    assert get_endpoint.call_args_list[1][1]["data"]["cursor"] == "cursor-2"


def test_make_request_handles_problem_json(module_factory):
    module = module_factory()
    response = MagicMock()
    response.read.return_value = json.dumps({"detail": "Unauthorized"}).encode("utf-8")
    response.getcode.return_value = 401

    with patch.object(module.session, "open", return_value=response):
        with pytest.raises(SystemExit):
            module.make_request("GET", "projects")
