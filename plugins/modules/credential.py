#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# This module is implemented as an action plugin (see plugins/action/credential.py).

DOCUMENTATION = r"""
---
module: credential
short_description: Manage Automation Orchestrator credentials
description:
  - Create, update, or delete credentials in Automation Orchestrator.
author:
  - Tom Page (@Tompage1994)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
  - infra.automation_orchestrator.state
options:
  name:
    description:
      - Name of the credential.
    required: true
    type: str
  credential_type:
    description:
      - Credential type name or ID.
      - Required when creating a credential.
    type: str
  project:
    description:
      - Project name or ID.
      - Required when creating a credential. Immutable after creation.
    type: str
  description:
    description:
      - Credential description.
    type: str
  inputs:
    description:
      - Credential input values as defined by the credential type.
      - Required when creating a credential.
      - Use V($encrypted$) for secret fields you want to preserve without changing.
    type: dict
  enabled:
    description:
      - Whether the credential is enabled.
    type: bool
  labels:
    description:
      - Key-value labels for the credential.
    type: dict
  update_secrets:
    description:
      - When C(false), secret fields set to V($encrypted$) are not sent to the API on update.
    type: bool
    default: false
    aliases: [update_inputs]
"""

EXAMPLES = r"""
- name: Create a bearer token credential
  infra.automation_orchestrator.credential:
    ao_host: https://orchestrator.example.com
    ao_username: admin
    ao_password: secret
    ao_validate_certs: false
    name: api-token
    credential_type: HTTP Bearer Token
    project: my-project
    inputs:
      token: "{{ vault_token }}"
    state: present

- name: Update credential without changing the secret
  infra.automation_orchestrator.credential:
    name: api-token
    enabled: true
    inputs:
      token: $encrypted$
    state: present

- name: Delete a credential
  infra.automation_orchestrator.credential:
    name: api-token
    state: absent
"""

RETURN = r"""
id:
  description: Credential ID.
  returned: success
  type: str
credential:
  description: Credential object returned by the API.
  returned: success
  type: dict
"""
