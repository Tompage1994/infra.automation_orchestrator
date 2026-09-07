#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# This module is implemented as an action plugin (see plugins/action/project.py).

DOCUMENTATION = r"""
---
module: project
short_description: Manage Automation Orchestrator projects
description:
  - Create, update, or delete projects in Automation Orchestrator.
author:
  - Tom Page (@Tompage1994)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
  - infra.automation_orchestrator.state
options:
  name:
    description:
      - Name of the project.
    required: true
    type: str
  description:
    description:
      - Project description.
    type: str
  labels:
    description:
      - Key-value labels for the project.
    type: dict
"""

EXAMPLES = r"""
- name: Create a project
  infra.automation_orchestrator.project:
    ao_host: https://orchestrator.example.com
    ao_username: admin
    ao_password: secret
    ao_validate_certs: false
    name: my-project
    description: Example project
    state: present

- name: Delete a project
  infra.automation_orchestrator.project:
    name: my-project
    state: absent
"""

RETURN = r"""
id:
  description: Project ID.
  returned: success
  type: str
project:
  description: Project object returned by the API.
  returned: success
  type: dict
"""
