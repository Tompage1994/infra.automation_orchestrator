#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: project
short_description: Manage Automation Orchestrator projects
description:
  - Create, update, or delete projects in Automation Orchestrator.
author:
  - Tom Page (@tpage)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
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
  state:
    description:
      - Desired state of the project.
    choices: [present, absent, exists]
    default: present
    type: str
"""

EXAMPLES = r"""
- name: Create a project
  infra.automation_orchestrator.project:
    orchestrator_host: https://orchestrator.example.com
    orchestrator_username: admin
    orchestrator_password: secret
    validate_certs: false
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
  returned: when state is present and not check mode
  type: dict
"""

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import OrchestratorModule


def main():
    argument_spec = dict(
        name=dict(required=True),
        description=dict(),
        labels=dict(type="dict"),
        state=dict(choices=["present", "absent", "exists"], default="present"),
    )

    module = OrchestratorModule(argument_spec=argument_spec)
    endpoint = "projects"

    existing_item = module.get_one(endpoint, name_or_id=module.params["name"])

    if module.params["state"] == "absent":
        module.delete_if_needed(existing_item, endpoint, item_type="project")

    if module.params["state"] == "exists":
        module.get_one(endpoint, name_or_id=module.params["name"], allow_none=False, check_exists=True)

    new_item = {"name": module.params["name"]}
    if module.params["description"] is not None:
        new_item["description"] = module.params["description"]
    if module.params["labels"] is not None:
        new_item["labels"] = module.params["labels"]

    result = module.create_or_update_if_needed(
        existing_item,
        new_item,
        endpoint=endpoint,
        item_type="project",
        auto_exit=False,
    )
    module.json_output["project"] = result
    module.exit_json(**module.json_output)


if __name__ == "__main__":
    main()
