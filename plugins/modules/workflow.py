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
  - Workflows are graphs. C(triggers) start a run, C(nodes) are the steps, and C(edges) connect them.
  - There is no separate add-node or remove-node operation. To change steps, pass a complete replacement C(workflow_definition).
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
      - Complete workflow graph (schema version 2.0.0). Required when creating a workflow.
      - Top-level keys are C(schema_version), C(name), C(description), C(triggers), C(nodes), and C(edges).
      - C(triggers) start the workflow. Each trigger needs a unique C(id) and a C(type) such as C(manual_trigger).
        Triggers are not listed under C(nodes); edges reference them by C(id).
      - C(nodes) are the workflow steps. Each node needs a unique C(id), a C(type), and C(parameters) for that type.
        Optional C(name), C(description), and C(position) (C(x)/C(y)) are used by the designer.
      - Common node types include C(wait), C(script), C(http_request), C(condition), C(switch), C(loop), C(converge),
        C(approval), C(agentic), C(aap_job_template), and C(aap_workflow_job_template).
      - C(wait) nodes require C(parameters.duration) in seconds. C(condition) nodes require C(parameters.condition)
        and use C(from_port) on outgoing edges (C(true) or C(false)).
      - C(agentic) (task agent) nodes require C(parameters.prompt). Optional fields include C(llm_model_id),
        C(tool_selection_strategy) (C(ALL), C(NONE), or C(SELECTED)), and C(integration_connections).
        Each integration connection needs C(integration_id) and C(credential_id) and must reference an MCP server
        integration. Use C(tool_selection_strategy) C(NONE) when the node should not call MCP tools.
      - C(aap_job_template) nodes launch an Ansible Automation Platform job template. Set C(credential_id) to an
        Ansible Automation Platform credential (which includes the AAP host). Optional C(integration_id) identifies
        the C(ansible_automation_platform) integration. Provide either C(job_template_id) or
        C(job_template_name) with C(organization_name).
      - C(edges) connect steps. Each edge has C(from) (source trigger or node ID) and C(to) (target node ID).
      - To add, remove, or reconnect steps, replace the whole graph. Include every node you want to keep, omit
        nodes you want to remove, and keep C(edges) consistent with the remaining IDs.
      - Node and trigger IDs must match C(^[a-zA-Z_][a-zA-Z0-9_]*$).
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
  state:
    description:
      - Desired state of the workflow.
    choices: [present, absent, exists]
    default: present
    type: str
notes:
  - Updating C(workflow_definition) creates a new workflow version when the graph differs from the current version.
  - Metadata-only updates (name, description, labels) do not create a new version.
  - Retrieve the saved graph from the returned C(workflow.version.workflow_definition) after an update, or with
    GET C(/api/v1/workflows/{id}). Create responses do not include the nested version object.
"""

EXAMPLES = r"""
- name: Create a minimal manual-trigger workflow with no steps
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

- name: Create a workflow with two sequential wait steps
  infra.automation_orchestrator.workflow:
    name: sequential-waits
    project: my-project
    description: Trigger then two wait steps
    workflow_definition:
      name: sequential-waits
      schema_version: "2.0.0"
      description: Trigger then two wait steps
      triggers:
        - id: trigger_1
          name: Trigger
          type: manual_trigger
          parameters: {}
      nodes:
        - id: wait_first
          name: First wait
          type: wait
          parameters:
            duration: 1
        - id: wait_second
          name: Second wait
          type: wait
          parameters:
            duration: 1
      edges:
        - from: trigger_1
          to: wait_first
        - from: wait_first
          to: wait_second
    state: present

- name: Add a third wait step by replacing the workflow graph
  infra.automation_orchestrator.workflow:
    name: sequential-waits
    project: my-project
    change_description: Add wait_third after wait_second
    workflow_definition:
      name: sequential-waits
      schema_version: "2.0.0"
      description: Trigger then three wait steps
      triggers:
        - id: trigger_1
          name: Trigger
          type: manual_trigger
          parameters: {}
      nodes:
        - id: wait_first
          name: First wait
          type: wait
          parameters:
            duration: 1
        - id: wait_second
          name: Second wait
          type: wait
          parameters:
            duration: 1
        - id: wait_third
          name: Third wait
          type: wait
          parameters:
            duration: 1
      edges:
        - from: trigger_1
          to: wait_first
        - from: wait_first
          to: wait_second
        - from: wait_second
          to: wait_third
    state: present

- name: Remove wait_third by omitting it from the replacement graph
  infra.automation_orchestrator.workflow:
    name: sequential-waits
    project: my-project
    change_description: Remove wait_third
    workflow_definition:
      name: sequential-waits
      schema_version: "2.0.0"
      description: Trigger then two wait steps
      triggers:
        - id: trigger_1
          name: Trigger
          type: manual_trigger
          parameters: {}
      nodes:
        - id: wait_first
          name: First wait
          type: wait
          parameters:
            duration: 1
        - id: wait_second
          name: Second wait
          type: wait
          parameters:
            duration: 1
      edges:
        - from: trigger_1
          to: wait_first
        - from: wait_first
          to: wait_second
    state: present

- name: Create a workflow with a condition and two branches
  infra.automation_orchestrator.workflow:
    name: conditional-waits
    project: my-project
    workflow_definition:
      name: conditional-waits
      schema_version: "2.0.0"
      description: Branch on a condition into two wait steps
      triggers:
        - id: trigger_1
          type: manual_trigger
          parameters: {}
      nodes:
        - id: check
          name: Always true
          type: condition
          parameters:
            condition: "1 == 1"
        - id: wait_true
          name: True branch
          type: wait
          parameters:
            duration: 1
        - id: wait_false
          name: False branch
          type: wait
          parameters:
            duration: 1
      edges:
        - from: trigger_1
          to: check
        - from: check
          to: wait_true
          from_port: "true"
        - from: check
          to: wait_false
          from_port: "false"
    state: present

- name: Create a workflow with a task agent and an MCP integration connection
  infra.automation_orchestrator.workflow:
    name: task-agent-workflow
    project: my-project
    description: Analyze input with a task agent
    workflow_definition:
      name: task-agent-workflow
      schema_version: "2.0.0"
      description: Analyze input with a task agent
      triggers:
        - id: trigger_1
          type: manual_trigger
          parameters: {}
      nodes:
        - id: analyze
          name: Analyze
          type: agentic
          parameters:
            prompt: Summarize the incoming request and recommend a job template.
            tool_selection_strategy: NONE
            integration_connections:
              - integration_id: "{{ mcp_integration_id }}"
                credential_id: "{{ mcp_credential_id }}"
      edges:
        - from: trigger_1
          to: analyze
    state: present

- name: Create a workflow that launches an AAP job template
  infra.automation_orchestrator.workflow:
    name: aap-job-workflow
    project: my-project
    description: Launch an Ansible Automation Platform job template
    workflow_definition:
      name: aap-job-workflow
      schema_version: "2.0.0"
      description: Launch an Ansible Automation Platform job template
      triggers:
        - id: trigger_1
          type: manual_trigger
          parameters: {}
      nodes:
        - id: launch_job
          name: Launch job template
          type: aap_job_template
          parameters:
            integration_id: "{{ aap_integration_id }}"
            credential_id: "{{ aap_credential_id }}"
            job_template_name: Demo Job Template
            organization_name: Default
      edges:
        - from: trigger_1
          to: launch_job
    state: present
"""

RETURN = r"""
id:
  description: Workflow ID.
  returned: success
  type: str
workflow:
  description:
    - Workflow object returned by the API.
    - Create returns metadata only. Update returns the current version, including the graph at
      C(version.workflow_definition) with C(triggers), C(nodes), and C(edges).
  returned: when state is present and not check mode
  type: dict
  contains:
    id:
      description: Workflow ID.
      type: str
    name:
      description: Workflow name.
      type: str
    current_version:
      description: Latest workflow version number.
      type: int
    version:
      description:
        - Current workflow version. Present on get and update responses.
      type: dict
      contains:
        workflow_definition:
          description: Graph definition with C(triggers), C(nodes), and C(edges).
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
