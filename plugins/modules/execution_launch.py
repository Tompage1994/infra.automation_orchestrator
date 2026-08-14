#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: execution_launch
short_description: Launch a workflow execution in Automation Orchestrator
description:
  - Trigger a workflow execution and optionally wait for it to complete.
author:
  - Tom Page (@tpage)
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
      - Initial polling interval in seconds when waiting.
    type: float
    default: 2
"""

EXAMPLES = r"""
- name: Launch a workflow execution and wait
  infra.automation_orchestrator.execution_launch:
    orchestrator_host: https://orchestrator.example.com
    orchestrator_username: admin
    orchestrator_password: secret
    validate_certs: false
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

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import OrchestratorModule


def resolve_project_id(module, project):
    if module.is_uuid(project):
        return project
    return module.resolve_name_to_id("projects", project)


def main():
    argument_spec = dict(
        workflow=dict(required=True),
        project=dict(),
        trigger_node_id=dict(required=True),
        input_data=dict(type="dict", default={}),
        use_published=dict(type="bool", default=False),
        wait=dict(type="bool", default=False),
        timeout=dict(type="int", default=300),
        interval=dict(type="float", default=2),
    )

    module = OrchestratorModule(argument_spec=argument_spec)

    lookup_filters = {}
    if module.params["project"]:
        lookup_filters["project_id[eq]"] = resolve_project_id(module, module.params["project"])

    workflow = module.get_exactly_one("workflows", module.params["workflow"], **lookup_filters)

    launch_data = {
        "workflow_id": workflow["id"],
        "trigger_node_id": module.params["trigger_node_id"],
        "input_data": module.params["input_data"],
        "use_published": module.params["use_published"],
    }

    if module.check_mode:
        module.json_output["changed"] = True
        module.json_output["execution_id"] = "check-mode"
        module.exit_json(**module.json_output)

    response = module.post_endpoint("executions", data=launch_data)
    if response["status_code"] not in (200, 201):
        detail = response["json"].get("detail", response["json"]) if isinstance(response["json"], dict) else response["json"]
        module.fail_json(msg="Unable to launch execution: {0}".format(detail), response=response)

    execution = response["json"]
    module.json_output["changed"] = True
    module.json_output["execution_id"] = execution["id"]
    module.json_output["status"] = execution.get("status")
    module.json_output["execution"] = execution

    if module.params["wait"]:
        execution = module.wait_on_execution(
            execution["id"],
            timeout=module.params["timeout"],
            interval=module.params["interval"],
        )
        module.json_output["execution"] = execution

    module.exit_json(**module.json_output)


if __name__ == "__main__":
    main()
