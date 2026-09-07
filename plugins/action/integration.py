#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError

from ansible_collections.infra.automation_orchestrator.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.ansible_models.integration import AnsibleIntegration


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "integration"
    MODEL_CLASS = AnsibleIntegration

    def _resolve_lookup(self, resource, resource_data, validated_params):
        if resource.management_credential:
            resolved = self._client.resolve_id("/api/v1/credentials", resource.management_credential, what="management_credential")
            resource.management_credential = resolved
            resource_data["management_credential"] = resolved

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        if operation == "create":
            if not ansible_data.get("integration_type"):
                raise AnsibleError("integration_type is required when creating an integration")
            if ansible_data.get("configuration") is None:
                raise AnsibleError("configuration is required when creating an integration")
