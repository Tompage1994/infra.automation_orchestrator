#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: credential
short_description: Manage Automation Orchestrator credentials
description:
  - Create, update, or delete credentials in Automation Orchestrator.
author:
  - Tom Page (@tpage)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth
options:
  name:
    description:
      - Name of the credential.
    required: true
    type: str
  credential_type:
    description:
      - Credential type name or ID.
    type: str
  project:
    description:
      - Project name or ID. Required when creating a credential.
    type: str
  description:
    description:
      - Credential description.
    type: str
  inputs:
    description:
      - Credential input values as defined by the credential type.
      - Ansible Automation Platform credentials require C(host) plus either C(oauth_token) or C(username) and C(password).
      - Use V($encrypted$) for secret fields you want to preserve without changing.
    type: dict
  enabled:
    description:
      - Whether the credential is enabled.
    type: bool
    default: true
  labels:
    description:
      - Key-value labels for the credential.
    type: dict
  update_secrets:
    description:
      - When false, secret fields set to V($encrypted$) are not updated.
    type: bool
    default: false
    aliases: [update_inputs]
  state:
    description:
      - Desired state of the credential.
    choices: [present, absent, exists]
    default: present
    type: str
"""

EXAMPLES = r"""
- name: Create a bearer token credential
  infra.automation_orchestrator.credential:
    orchestrator_host: https://orchestrator.example.com
    orchestrator_username: admin
    orchestrator_password: secret
    validate_certs: false
    name: api-token
    credential_type: HTTP Bearer Token
    project: my-project
    inputs:
      token: "{{ vault_token }}"
    state: present

- name: Create an Ansible Automation Platform credential
  infra.automation_orchestrator.credential:
    name: aap-token
    credential_type: Ansible Automation Platform
    project: my-project
    inputs:
      host: https://aap.example.com
      oauth_token: "{{ vault_aap_token }}"
    state: present

- name: Update credential without changing the secret
  infra.automation_orchestrator.credential:
    name: api-token
    enabled: true
    inputs:
      token: $encrypted$
    state: present
"""

RETURN = r"""
id:
  description: Credential ID.
  returned: success
  type: str
credential:
  description: Credential object returned by the API.
  returned: when state is present and not check mode
  type: dict
"""

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import OrchestratorAPIModule


def resolve_credential_type(module, credential_type):
    if module.is_uuid(credential_type):
        return credential_type
    item = module.get_exactly_one("credential_types", credential_type)
    return item["id"]


def resolve_project_id(module, project):
    if module.is_uuid(project):
        return project
    return module.resolve_name_to_id("projects", project)


def main():
    argument_spec = dict(
        name=dict(required=True),
        credential_type=dict(),
        project=dict(),
        description=dict(),
        inputs=dict(type="dict", no_log=True),
        enabled=dict(type="bool", default=True),
        labels=dict(type="dict"),
        state=dict(choices=["present", "absent", "exists"], default="present"),
    )

    module = OrchestratorAPIModule(argument_spec=argument_spec)
    endpoint = "credentials"

    existing_item = module.get_one(endpoint, name_or_id=module.params["name"])

    if module.params["state"] == "absent":
        module.delete_if_needed(existing_item, endpoint, item_type="credential")

    if module.params["state"] == "exists":
        module.get_one(endpoint, name_or_id=module.params["name"], allow_none=False, check_exists=True)

    if existing_item is None:
        if not module.params["credential_type"]:
            module.fail_json(msg="credential_type is required when creating a credential")
        if not module.params["project"]:
            module.fail_json(msg="project is required when creating a credential")
        if module.params["inputs"] is None:
            module.fail_json(msg="inputs is required when creating a credential")

    new_item = {"name": module.params["name"]}
    if module.params["description"] is not None:
        new_item["description"] = module.params["description"]
    if module.params["labels"] is not None:
        new_item["labels"] = module.params["labels"]
    if module.params["enabled"] is not None:
        new_item["enabled"] = module.params["enabled"]
    if module.params["inputs"] is not None:
        new_item["inputs"] = module.params["inputs"]

    if existing_item is None:
        new_item["credential_type_id"] = resolve_credential_type(module, module.params["credential_type"])
        new_item["project_id"] = resolve_project_id(module, module.params["project"])
    elif module.params["credential_type"] is not None:
        new_item["credential_type_id"] = resolve_credential_type(module, module.params["credential_type"])

    result = module.create_or_update_if_needed(
        existing_item,
        new_item,
        endpoint=endpoint,
        item_type="credential",
        auto_exit=False,
    )
    module.json_output["credential"] = result
    module.exit_json(**module.json_output)


if __name__ == "__main__":
    main()
