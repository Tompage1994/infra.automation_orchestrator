# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.infra.automation_orchestrator.plugins.action.workflow import _current_definition


def test_current_definition_extracts_nested_graph():
    existing = {"id": "wf-1", "version": {"workflow_definition": {"nodes": []}}}
    assert _current_definition(existing) == {"nodes": []}


def test_current_definition_handles_missing_version():
    assert _current_definition({"id": "wf-1"}) == {}


def test_current_definition_handles_none():
    assert _current_definition(None) == {}
