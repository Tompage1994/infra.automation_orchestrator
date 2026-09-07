# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""API v1 project dataclass and transform mixin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APIProject_v1:
    name: Optional[str] = None
    description: Optional[str] = None
    labels: Optional[dict] = None
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for the project resource, API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: Any, context: Union[TransformContext, Dict[str, Any]]) -> "APIProject_v1":
        api_data: Dict[str, Any] = {"name": getattr(ansible_instance, "name", None)}
        description = getattr(ansible_instance, "description", None)
        if description is not None:
            api_data["description"] = description
        labels = getattr(ansible_instance, "labels", None)
        if labels is not None:
            api_data["labels"] = labels
        resource_id = getattr(ansible_instance, "id", None)
        if resource_id is not None:
            api_data["id"] = resource_id
        return APIProject_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(path="/api/v1/projects", method="POST", fields=["name", "description", "labels"], required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/v1/projects/{id}", method="PATCH", fields=["name", "description", "labels"], path_params=["id"], required_for="update", order=1
            ),
            "delete": EndpointOperation(path="/api/v1/projects/{id}", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1),
            "get": EndpointOperation(path="/api/v1/projects/{id}", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/v1/projects", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        from ...ansible_models.project import AnsibleProject

        return AnsibleProject(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            labels=api_data.get("labels"),
            id=api_data.get("id"),
            created_at=api_data.get("created_at"),
            updated_at=api_data.get("updated_at"),
        )
