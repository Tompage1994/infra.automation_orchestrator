#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

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
options:
  name:
    description:
      - Name of the integration.
    required: true
    type: str
  integration_type:
    description:
      - Integration type, such as C(ansible_automation_platform), C(mcp_server), or C(llm_provider).
    type: str
  configuration:
    description:
      - Integration configuration object passed through to the API.
      - Ansible Automation Platform integrations require C(aap_url). C(base_url) is accepted as an alias and rewritten to C(aap_url).
    type: dict
  description:
    description:
      - Integration description.
    type: str
  enabled:
    description:
      - Whether the integration is enabled.
    type: bool
    default: true
  scope:
    description:
      - Integration visibility scope.
    choices: [global, project]
    default: global
    type: str
  management_credential:
    description:
      - Management credential name or ID.
    type: str
  labels:
    description:
      - Key-value labels for the integration.
    type: dict
  state:
    description:
      - Desired state of the integration.
    choices: [present, absent, exists]
    default: present
    type: str
"""

EXAMPLES = r"""
- name: Create an LLM provider integration
  infra.automation_orchestrator.integration:
    orchestrator_host: https://orchestrator.example.com
    orchestrator_username: admin
    orchestrator_password: secret
    validate_certs: false
    name: my-llm
    integration_type: llm_provider
    configuration:
      integration_type: llm_provider
      provider_hint: custom
      base_url: https://llm.example.com/v1
    management_credential: api-token
    state: present

- name: Create an Ansible Automation Platform integration
  infra.automation_orchestrator.integration:
    name: my-aap
    integration_type: ansible_automation_platform
    configuration:
      integration_type: ansible_automation_platform
      aap_url: https://aap.example.com
    management_credential: aap-token
    state: present
"""

RETURN = r"""
id:
  description: Integration ID.
  returned: success
  type: str
integration:
  description: Integration object returned by the API.
  returned: when state is present and not check mode
  type: dict
"""

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import OrchestratorModule


def resolve_credential_id(module, credential):
    if module.is_uuid(credential):
        return credential
    return module.resolve_name_to_id("credentials", credential)


def normalize_configuration(configuration, integration_type):
    if not configuration:
        return configuration
    config = dict(configuration)
    config_type = config.get("integration_type") or integration_type
    if config_type in ("ansible_automation_platform", "aap_gateway") and "base_url" in config:
        config.setdefault("aap_url", config["base_url"])
        config.pop("base_url")
    return config


def main():
    argument_spec = dict(
        name=dict(required=True),
        integration_type=dict(),
        configuration=dict(type="dict"),
        description=dict(),
        enabled=dict(type="bool", default=True),
        scope=dict(choices=["global", "project"], default="global"),
        management_credential=dict(),
        labels=dict(type="dict"),
        state=dict(choices=["present", "absent", "exists"], default="present"),
    )

    module = OrchestratorModule(argument_spec=argument_spec)
    endpoint = "integrations"

    existing_item = module.get_one(endpoint, name_or_id=module.params["name"])

    if module.params["state"] == "absent":
        module.delete_if_needed(existing_item, endpoint, item_type="integration")

    if module.params["state"] == "exists":
        module.get_one(endpoint, name_or_id=module.params["name"], allow_none=False, check_exists=True)

    if existing_item is None:
        if not module.params["integration_type"]:
            module.fail_json(msg="integration_type is required when creating an integration")
        if module.params["configuration"] is None:
            module.fail_json(msg="configuration is required when creating an integration")

    new_item = {"name": module.params["name"]}
    if module.params["description"] is not None:
        new_item["description"] = module.params["description"]
    if module.params["labels"] is not None:
        new_item["labels"] = module.params["labels"]
    if module.params["enabled"] is not None:
        new_item["enabled"] = module.params["enabled"]
    if module.params["scope"] is not None:
        new_item["scope"] = module.params["scope"]
    if module.params["configuration"] is not None:
        new_item["configuration"] = normalize_configuration(
            module.params["configuration"],
            module.params["integration_type"],
        )

    if existing_item is None:
        new_item["integration_type"] = module.params["integration_type"]
        if module.params["management_credential"] is not None:
            new_item["management_credential_id"] = resolve_credential_id(module, module.params["management_credential"])
    elif module.params["management_credential"] is not None:
        new_item["management_credential_id"] = resolve_credential_id(module, module.params["management_credential"])

    result = module.create_or_update_if_needed(
        existing_item,
        new_item,
        endpoint=endpoint,
        item_type="integration",
        auto_exit=False,
    )
    module.json_output["integration"] = result
    module.exit_json(**module.json_output)


if __name__ == "__main__":
    main()
