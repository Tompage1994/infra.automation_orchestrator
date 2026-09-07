# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.config import AOConfig, extract_ao_config


def test_ao_config_normalizes_url_without_scheme():
    config = AOConfig(base_url="ao.example.com")
    assert config.base_url == "https://ao.example.com"


def test_ao_config_preserves_http_scheme_and_strips_trailing_slash():
    config = AOConfig(base_url="http://ao.example.com/")
    assert config.base_url == "http://ao.example.com"


def test_extract_ao_config_from_task_args(monkeypatch):
    monkeypatch.delenv("AO_HOST", raising=False)
    config = extract_ao_config(task_args={"ao_host": "ao.example.com", "ao_username": "admin", "ao_password": "secret"})
    assert config.base_url == "https://ao.example.com"
    assert config.username == "admin"
    assert config.password == "secret"
    assert config.verify_ssl is True


def test_extract_ao_config_task_args_override_host_vars():
    config = extract_ao_config(
        task_args={"ao_host": "task.example.com"},
        host_vars={"ao_host": "hostvars.example.com"},
    )
    assert config.base_url == "https://task.example.com"


def test_extract_ao_config_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("AO_HOST", "env.example.com")
    monkeypatch.setenv("AO_TOKEN", "env-token")
    config = extract_ao_config(task_args={}, host_vars={})
    assert config.base_url == "https://env.example.com"
    assert config.token == "env-token"


def test_extract_ao_config_validate_certs_false_is_not_dropped():
    config = extract_ao_config(task_args={"ao_host": "ao.example.com", "ao_validate_certs": False})
    assert config.verify_ssl is False


def test_extract_ao_config_raises_when_host_missing(monkeypatch):
    monkeypatch.delenv("AO_HOST", raising=False)
    with pytest.raises(ValueError):
        extract_ao_config(task_args={}, host_vars={}, required=True)


def test_extract_ao_config_token_dict_extracts_string(monkeypatch):
    monkeypatch.delenv("AO_HOST", raising=False)
    config = extract_ao_config(task_args={"ao_host": "ao.example.com", "ao_token": {"token": "abc123"}})
    assert config.token == "abc123"
