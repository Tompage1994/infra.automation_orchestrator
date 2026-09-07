#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# This module is implemented as an action plugin (see plugins/action/workflow.py).

DOCUMENTATION = r"""
---
module: workflow
short_description: Manage Automation Orchestrator workflows
description:
  - Create, update, delete, publish, or unpublish workflow definitions in Automation Orchestrator.
  - Workflows are graphs. C(triggers) start a run, C(nodes) are the steps, and C(edges) connect them.
  - There is no separate add-node or remove-node operation. To change steps, pass a complete replacement C(workflow_definition).
  - Fields inside C(workflow_definition) that normally hold a UUID (C(credential_id), C(integration_id),
    C(project_id), C(llm_model_id)) may instead be given as C(credential), C(integration), C(project), or
    C(llm_model) with a human-readable name; the name is resolved to its UUID before the definition is saved.
author:
  - Tom Page (@tpage)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
  - infra.automation_orchestrator.state
options:
  name:
    description:
      - Name of the workflow.
    required: true
    type: str
  project:
    description:
      - Project name or ID. Required when creating a workflow and recommended when looking up by name.
    type: str
  description:
    description:
      - Workflow description.
    type: str
  labels:
    description:
      - Key-value labels for the workflow.
    type: dict
  workflow_definition:
    description:
      - Complete workflow graph (schema version 2.0.0). Required when creating a workflow.
    type: dict
  change_description:
    description:
      - Description of changes when updating the workflow definition.
      - Stored on the new workflow version created when the graph changes.
    type: str
  expected_version:
    description:
      - Expected workflow version for optimistic concurrency on update.
    type: int
  published:
    description:
      - When C(true), publish the current version after saving.
      - When C(false), unpublish the workflow if a published version exists.
      - When omitted, publish state is left unchanged.
    type: bool
  validate:
    description:
      - Call C(POST /api/v1/workflows/validate) before create/update.
    type: bool
    default: true
  allow_builtin:
    description:
      - Allow creating, updating, or deleting a builtin workflow.
    type: bool
    default: false
notes:
  - Updating C(workflow_definition) creates a new workflow version when the graph differs from the current version.
  - Metadata-only updates (name, description, labels) do not create a new version.
  - C(project) is immutable after creation and is never sent on update.
"""

EXAMPLES = r"""
- name: Create and publish a minimal manual-trigger workflow
  infra.automation_orchestrator.workflow:
    ao_host: https://orchestrator.example.com
    ao_username: admin
    ao_password: secret
    ao_validate_certs: false
    name: hello-workflow
    project: my-project
    description: Simple workflow
    published: true
    workflow_definition:
      schema_version: "2.0.0"
      name: hello-workflow
      triggers:
        - id: trigger_1
          name: Trigger
          type: manual_trigger
          parameters: {}
      nodes: []
      edges: []
    state: present

- name: Delete a workflow
  infra.automation_orchestrator.workflow:
    name: hello-workflow
    project: my-project
    state: absent
"""

RETURN = r"""
id:
  description: Workflow ID.
  returned: success
  type: str
workflow:
  description:
    - Workflow object returned by the API, including C(version.workflow_definition) with the current graph.
  returned: success
  type: dict
"""
