# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""API v1 credential dataclass and transform mixin.

Foreign keys (``credential_type``, ``project``) are resolved to UUIDs by the
action plugin's ``_resolve_lookup`` hook before this mixin ever runs, so
``from_ansible_data`` only has to rename them to their ``*_id`` API field
names. ``project_id`` is immutable after creation, so it is only sent on
create. ``inputs`` sanitisation (``$encrypted$`` handling) is done by the
action plugin's ``_pre_execute_hook`` before ``execute()`` is called.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APICredential_v1:
    name: Optional[str] = None
    description: Optional[str] = None
    labels: Optional[dict] = None
    inputs: Optional[dict] = None
    enabled: Optional[bool] = None
    credential_type_id: Optional[str] = None
    project_id: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CredentialTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for the credential resource, API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: Any, context: Union[TransformContext, Dict[str, Any]]) -> "APICredential_v1":
        operation = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")

        api_data: Dict[str, Any] = {"name": getattr(ansible_instance, "name", None)}
        for field_name in ("description", "labels", "inputs", "enabled"):
            value = getattr(ansible_instance, field_name, None)
            if value is not None:
                api_data[field_name] = value

        credential_type = getattr(ansible_instance, "credential_type", None)
        if credential_type is not None:
            api_data["credential_type_id"] = credential_type

        project = getattr(ansible_instance, "project", None)
        if project is not None and operation == "create":
            api_data["project_id"] = project

        resource_id = getattr(ansible_instance, "id", None)
        if resource_id is not None:
            api_data["id"] = resource_id

        return APICredential_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = ["name", "description", "labels", "inputs", "enabled", "credential_type_id", "project_id"]
        return {
            "create": EndpointOperation(path="/api/v1/credentials", method="POST", fields=fields, required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/v1/credentials/{id}",
                method="PATCH",
                fields=[f for f in fields if f != "project_id"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(path="/api/v1/credentials/{id}", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1),
            "get": EndpointOperation(path="/api/v1/credentials/{id}", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/v1/credentials", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        from ...ansible_models.credential import AnsibleCredential

        return AnsibleCredential(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            labels=api_data.get("labels"),
            inputs=api_data.get("inputs"),
            enabled=api_data.get("enabled"),
            credential_type=api_data.get("credential_type_id"),
            project=api_data.get("project_id"),
            id=api_data.get("id"),
            created_at=api_data.get("created_at"),
            updated_at=api_data.get("updated_at"),
        )
