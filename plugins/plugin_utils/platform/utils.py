# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared helpers for Automation Orchestrator data handling.

Merges patterns from both predecessor collections:
- ``is_uuid`` from ``infra.automation_orchestrator`` (Tom's OrchestratorModule)
- ``sanitize_inputs``, ``walk_rewrite``, ``drop_readonly``, ``values_equal``,
  and the builtin-object guard from ``lennysh.ao_configuration`` (ao_api.py / ao_crud.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import UUID

ENCRYPTED = "$encrypted$"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

# Fields returned by the API that are always server-managed and must never be
# sent back on create/update.
READONLY_FIELDS = frozenset(
    [
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "is_builtin",
        "is_default",
        "workflow_count",
        "integration_count",
        "credential_count",
        "member_count",
        "last_login",
        "last_validated_at",
        "last_refreshed_at",
        "last_successful_refresh_at",
        "validation_status",
        "validation_error",
        "refresh_status",
        "refresh_error",
        "total_tool_count",
        "enabled_tool_count",
        "total_model_count",
        "enabled_model_count",
        "has_validation_issues",
        "validation_result",
        "current_version",
        "published_version_id",
        "published_version_number",
        "version",
        "effective_value",
        "default_value",
        "cache_ttl_seconds",
        "requires_restart",
        "helper_text",
        "depends_on",
        "validation_schema",
        "value_type",
    ]
)

# Name-bearing fields inside a workflow definition, mapped to the *_id field
# the API actually expects. Used by walk_rewrite() to convert human-readable
# names to UUIDs (import) and back (export).
NAME_ALIASES = {
    "credential": "credential_id",
    "integration": "integration_id",
    "management_credential": "management_credential_id",
    "project": "project_id",
    "llm_model": "llm_model_id",
}

# Maps an *_id field found in a workflow definition to the (endpoint, name_field)
# used to resolve it to/from a human-readable name.
ID_TO_COLLECTION = {
    "credential_id": ("/api/v1/credentials", "name"),
    "management_credential_id": ("/api/v1/credentials", "name"),
    "integration_id": ("/api/v1/integrations", "name"),
    "project_id": ("/api/v1/projects", "name"),
}


def is_uuid(value: Any) -> bool:
    """Return True if value looks like a UUID string."""
    if not isinstance(value, str):
        return False
    if _UUID_RE.match(value):
        return True
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def drop_readonly(obj: Any, extra: Optional[Tuple[str, ...]] = None) -> Any:
    """Strip server-managed fields from an API response dict before re-sending it."""
    if not isinstance(obj, dict):
        return obj
    skip = READONLY_FIELDS.union(extra or ())
    return {k: v for k, v in obj.items() if k not in skip}


def values_equal(left: Any, right: Any) -> bool:
    """Deep equality that treats None and empty containers/strings as equivalent."""
    if left is None and right in ("", None, {}, []):
        return True
    if right is None and left in ("", None, {}, []):
        return True
    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left) | set(right)
        return all(values_equal(left.get(k), right.get(k)) for k in keys)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(values_equal(a, b) for a, b in zip(left, right))
    return left == right


def sanitize_inputs(desired: Optional[dict], existing: Optional[dict], update_secrets: bool = True) -> Tuple[dict, bool, bool]:
    """Reconcile a desired ``inputs``/secret dict against the existing (possibly masked) one.

    The API returns ``$encrypted$`` in place of any secret value on read. This
    helper never compares plaintext against ``$encrypted$`` (always assumed
    equal) and only forwards secret fields to the API when ``update_secrets``
    is set.

    Returns:
        (payload, visible_changed, force_secret_change)
    """
    desired = dict(desired or {})
    existing = dict(existing or {})
    comparable_desired: Dict[str, Any] = {}
    comparable_existing: Dict[str, Any] = {}
    secrets_to_send: Dict[str, Any] = {}
    for key, value in desired.items():
        if value == ENCRYPTED:
            continue
        current = existing.get(key)
        if current == ENCRYPTED:
            secrets_to_send[key] = value
            continue
        comparable_desired[key] = value
        comparable_existing[key] = current
    visible_changed = not values_equal(comparable_desired, comparable_existing)
    payload = dict(comparable_desired)
    force_secret_change = bool(update_secrets and secrets_to_send)
    if update_secrets:
        payload.update(secrets_to_send)
    return payload, visible_changed, force_secret_change


def walk_rewrite(obj: Any, rewriter: Callable[[str, Any], Any]) -> Any:
    """Recursively rewrite name-bearing fields inside a workflow definition.

    ``rewriter(id_key, value)`` is called for each ``*_id`` field (and for
    bare name fields listed in NAME_ALIASES, which are converted to their
    ``*_id`` counterpart first). Used for both name->id (import) and
    id->name (export) directions depending on the rewriter passed in.
    """
    if isinstance(obj, dict):
        data: Dict[str, Any] = {}
        pending_aliases: Dict[str, Any] = {}
        for key, value in obj.items():
            if key in NAME_ALIASES and not is_uuid(value):
                pending_aliases[NAME_ALIASES[key]] = value
                continue
            data[key] = walk_rewrite(value, rewriter)
        for id_key, name in pending_aliases.items():
            data[id_key] = rewriter(id_key, name)
        for id_key in list(data):
            if id_key in ID_TO_COLLECTION or id_key == "llm_model_id":
                data[id_key] = rewriter(id_key, data[id_key])
        return data
    if isinstance(obj, list):
        return [walk_rewrite(item, rewriter) for item in obj]
    return obj


def guard_builtin(existing: Optional[dict], allow_builtin: bool) -> Optional[str]:
    """Return an error message if a mutation would touch a builtin object, else None.

    Builtin objects (``is_builtin: true``) are unmanaged by default; pass
    ``allow_builtin=True`` on the module to explicitly opt in.
    """
    if existing and existing.get("is_builtin") and not allow_builtin:
        name = existing.get("name") or existing.get("id")
        return f"{name!r} is a builtin object; set allow_builtin=true to manage it"
    return None
