#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError

from ansible_collections.infra.automation_orchestrator.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.ansible_models.credential import AnsibleCredential
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.utils import sanitize_inputs


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "credential"
    MODEL_CLASS = AnsibleCredential
    _WRITE_ONLY_FIELDS = frozenset({"update_secrets"})

    def _resolve_lookup(self, resource, resource_data, validated_params):
        client = self._client
        if resource.credential_type:
            resolved = client.resolve_id("/api/v1/credential_types", resource.credential_type, what="credential_type")
            resource.credential_type = resolved
            resource_data["credential_type"] = resolved
        if resource.project:
            resolved = client.resolve_id("/api/v1/projects", resource.project, what="project")
            resource.project = resolved
            resource_data["project"] = resolved

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        if operation == "create":
            if not ansible_data.get("credential_type"):
                raise AnsibleError("credential_type is required when creating a credential")
            if not ansible_data.get("project"):
                raise AnsibleError("project is required when creating a credential")
            if ansible_data.get("inputs") is None:
                raise AnsibleError("inputs is required when creating a credential")
            return

        desired_inputs = ansible_data.get("inputs")
        if desired_inputs is not None:
            existing_inputs = (self._existing or {}).get("inputs") or {}
            update_secrets = bool(write_only_data.get("update_secrets", False))
            payload, _visible_changed, _force_secret_change = sanitize_inputs(desired_inputs, existing_inputs, update_secrets=update_secrets)
            ansible_data["inputs"] = payload
