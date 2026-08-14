#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: workflow
short_description: Manage Automation Orchestrator workflows
description:
  - Create, update, or delete workflow definitions in Automation Orchestrator.
author:
  - Tom Page (@tpage)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
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
      - Workflow definition object. Required when creating a workflow.
    type: dict
  change_description:
    description:
      - Description of changes when updating the workflow definition.
    type: str
  expected_version:
    description:
      - Expected workflow version for optimistic concurrency on update.
    type: int
  state:
    description:
      - Desired state of the workflow.
    choices: [present, absent, exists]
    default: present
    type: str
"""

EXAMPLES = r"""
- name: Create a minimal manual-trigger workflow
  infra.automation_orchestrator.workflow:
    orchestrator_host: https://orchestrator.example.com
    orchestrator_username: admin
    orchestrator_password: secret
    validate_certs: false
    name: hello-workflow
    project: my-project
    description: Simple workflow
    workflow_definition:
      name: hello-workflow
      schema_version: "2.0.0"
      description: Simple workflow
      triggers:
        - id: trigger_1
          name: Trigger
          type: manual_trigger
          position:
            x: 100
            y: 100
          parameters: {}
      nodes: []
      edges: []
    state: present
"""

RETURN = r"""
id:
  description: Workflow ID.
  returned: success
  type: str
workflow:
  description: Workflow object returned by the API.
  returned: when state is present and not check mode
  type: dict
"""

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import OrchestratorModule


def resolve_project_id(module, project):
    if module.is_uuid(project):
        return project
    return module.resolve_name_to_id("projects", project)


def main():
    argument_spec = dict(
        name=dict(required=True),
        project=dict(),
        description=dict(),
        labels=dict(type="dict"),
        workflow_definition=dict(type="dict"),
        change_description=dict(),
        expected_version=dict(type="int"),
        state=dict(choices=["present", "absent", "exists"], default="present"),
    )

    module = OrchestratorModule(argument_spec=argument_spec)
    endpoint = "workflows"

    lookup_filters = {}
    if module.params["project"]:
        lookup_filters["project_id[eq]"] = resolve_project_id(module, module.params["project"])

    existing_item = module.get_one(endpoint, name_or_id=module.params["name"], **lookup_filters)

    if module.params["state"] == "absent":
        module.delete_if_needed(existing_item, endpoint, item_type="workflow")

    if module.params["state"] == "exists":
        module.get_one(endpoint, name_or_id=module.params["name"], allow_none=False, check_exists=True, **lookup_filters)

    if existing_item is None:
        if not module.params["project"]:
            module.fail_json(msg="project is required when creating a workflow")
        if module.params["workflow_definition"] is None:
            module.fail_json(msg="workflow_definition is required when creating a workflow")

    new_item = {"name": module.params["name"]}
    if module.params["description"] is not None:
        new_item["description"] = module.params["description"]
    if module.params["labels"] is not None:
        new_item["labels"] = module.params["labels"]
    if module.params["workflow_definition"] is not None:
        new_item["workflow_definition"] = module.params["workflow_definition"]
    if module.params["change_description"] is not None:
        new_item["change_description"] = module.params["change_description"]
    if module.params["expected_version"] is not None:
        new_item["expected_version"] = module.params["expected_version"]

    if existing_item is None:
        new_item["project_id"] = resolve_project_id(module, module.params["project"])

    result = module.create_or_update_if_needed(
        existing_item,
        new_item,
        endpoint=endpoint,
        item_type="workflow",
        auto_exit=False,
    )
    module.json_output["workflow"] = result
    module.exit_json(**module.json_output)


if __name__ == "__main__":
    main()
