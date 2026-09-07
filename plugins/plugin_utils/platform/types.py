# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared type definitions for the Automation Orchestrator platform SDK."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .direct_client import AODirectClient


@dataclass
class EndpointOperation:
    """Configuration for a single API endpoint operation.

    Attributes:
        path: API endpoint path (e.g. '/api/v1/projects/').
        method: HTTP method ('GET', 'POST', 'PATCH', 'DELETE').
        fields: Dataclass field names to include in the request body.
        path_params: Path parameter names to substitute (e.g. ['id']).
        required_for: Operation type this is required for
            ('create', 'update', 'delete', or None for always).
        depends_on: Name of another operation this depends on.
        order: Execution order (lower runs first).
        flatten_body: If True, send the single dict field's value as the
            request body directly (used for singleton resources like settings).
    """

    path: str
    method: str
    fields: List[str]
    path_params: Optional[List[str]] = None
    required_for: Optional[str] = None
    depends_on: Optional[str] = None
    order: int = 0
    flatten_body: bool = False


@dataclass
class TransformContext:
    """Context passed to transform mixins for Ansible <-> API data conversion.

    Attributes:
        client: AODirectClient instance, used for FK name/id resolution.
        cache: Lookup cache (e.g. project/credential names <-> ids).
        api_version: Current API version string (always '1' for now).
        operation: Operation name ('create', 'update', 'delete', 'find').
    """

    client: "AODirectClient"
    cache: Dict[str, Any]
    api_version: str
    operation: Optional[str] = None
