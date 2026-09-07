#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# This module is implemented as an action plugin (see plugins/action/integration.py).

DOCUMENTATION = r"""
---
module: integration
short_description: Manage Automation Orchestrator integrations
description:
  - Create, update, or delete integrations in Automation Orchestrator.
author:
  - Tom Page (@tpage)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
  - infra.automation_orchestrator.state
options:
  name:
    description:
      - Name of the integration.
    required: true
    type: str
  integration_type:
    description:
      - Integration type, such as C(ansible_automation_platform), C(mcp_server), or C(llm_provider).
      - Required when creating an integration. Immutable after creation.
    type: str
  configuration:
    description:
      - Integration configuration object passed through to the API.
      - Required when creating an integration.
    type: dict
  description:
    description:
      - Integration description.
    type: str
  enabled:
    description:
      - Whether the integration is enabled.
    type: bool
  scope:
    description:
      - Integration visibility scope.
    choices: [global, project]
    type: str
  management_credential:
    description:
      - Management credential name or ID.
    type: str
  labels:
    description:
      - Key-value labels for the integration.
    type: dict
"""

EXAMPLES = r"""
- name: Create an LLM provider integration
  infra.automation_orchestrator.integration:
    ao_host: https://orchestrator.example.com
    ao_username: admin
    ao_password: secret
    ao_validate_certs: false
    name: my-llm
    integration_type: llm_provider
    configuration:
      provider_hint: custom
      base_url: https://llm.example.com/v1
    management_credential: api-token
    state: present

- name: Delete an integration
  infra.automation_orchestrator.integration:
    name: my-llm
    state: absent
"""

RETURN = r"""
id:
  description: Integration ID.
  returned: success
  type: str
integration:
  description: Integration object returned by the API.
  returned: success
  type: dict
"""
