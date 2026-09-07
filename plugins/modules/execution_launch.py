#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# This module is implemented as an action plugin (see plugins/action/execution_launch.py).

DOCUMENTATION = r"""
---
module: execution_launch
short_description: Launch a workflow execution in Automation Orchestrator
description:
  - Trigger a workflow execution and optionally wait for it to complete.
  - This is an action module, not a CRUD resource module; every successful run reports C(changed).
author:
  - Tom Page (@Tompage1994)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
options:
  workflow:
    description:
      - Workflow name or ID to execute.
    required: true
    type: str
  project:
    description:
      - Project name or ID. Recommended when looking up a workflow by name.
    type: str
  trigger_node_id:
    description:
      - Trigger node ID to start execution from.
    required: true
    type: str
  input_data:
    description:
      - Input data for the workflow execution.
    type: dict
    default: {}
  use_published:
    description:
      - Run the published workflow version instead of the current draft.
    type: bool
    default: false
  wait:
    description:
      - Wait for the execution to reach a terminal state.
    type: bool
    default: false
  timeout:
    description:
      - Timeout in seconds when waiting for execution completion.
    type: int
    default: 300
  interval:
    description:
      - Initial polling interval in seconds when waiting. Backs off up to 30 seconds.
    type: float
    default: 2
"""

EXAMPLES = r"""
- name: Launch a workflow execution and wait
  infra.automation_orchestrator.execution_launch:
    ao_host: https://orchestrator.example.com
    ao_username: admin
    ao_password: secret
    ao_validate_certs: false
    workflow: hello-workflow
    project: my-project
    trigger_node_id: trigger_1
    input_data:
      message: hello
    wait: true
    timeout: 600
"""

RETURN = r"""
execution_id:
  description: Execution ID.
  returned: success
  type: str
status:
  description: Execution status.
  returned: success
  type: str
execution:
  description: Execution object returned by the API.
  returned: success
  type: dict
"""
