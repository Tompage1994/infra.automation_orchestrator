# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""API v1 integration dataclass and transform mixin.

``management_credential`` is resolved to a UUID by the action plugin's
``_resolve_lookup`` hook before this mixin runs. ``integration_type`` is only
sent on create (it is immutable thereafter).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APIIntegration_v1:
    name: Optional[str] = None
    integration_type: Optional[str] = None
    configuration: Optional[dict] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    scope: Optional[str] = None
    management_credential_id: Optional[str] = None
    labels: Optional[dict] = None
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IntegrationTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for the integration resource, API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: Any, context: Union[TransformContext, Dict[str, Any]]) -> "APIIntegration_v1":
        operation = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")

        api_data: Dict[str, Any] = {"name": getattr(ansible_instance, "name", None)}
        for field_name in ("configuration", "description", "enabled", "scope", "labels"):
            value = getattr(ansible_instance, field_name, None)
            if value is not None:
                api_data[field_name] = value

        if operation == "create":
            api_data["integration_type"] = getattr(ansible_instance, "integration_type", None)

        management_credential = getattr(ansible_instance, "management_credential", None)
        if management_credential is not None:
            api_data["management_credential_id"] = management_credential

        resource_id = getattr(ansible_instance, "id", None)
        if resource_id is not None:
            api_data["id"] = resource_id

        return APIIntegration_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        create_fields = ["name", "integration_type", "configuration", "description", "enabled", "scope", "management_credential_id", "labels"]
        update_fields = [f for f in create_fields if f != "integration_type"]
        return {
            "create": EndpointOperation(path="/api/v1/integrations", method="POST", fields=create_fields, required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/v1/integrations/{id}", method="PATCH", fields=update_fields, path_params=["id"], required_for="update", order=1
            ),
            "delete": EndpointOperation(path="/api/v1/integrations/{id}", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1),
            "get": EndpointOperation(path="/api/v1/integrations/{id}", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/v1/integrations", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        from ...ansible_models.integration import AnsibleIntegration

        return AnsibleIntegration(
            name=api_data.get("name", ""),
            integration_type=api_data.get("integration_type"),
            configuration=api_data.get("configuration"),
            description=api_data.get("description"),
            enabled=api_data.get("enabled"),
            scope=api_data.get("scope"),
            management_credential=api_data.get("management_credential_id"),
            labels=api_data.get("labels"),
            id=api_data.get("id"),
            created_at=api_data.get("created_at"),
            updated_at=api_data.get("updated_at"),
        )
