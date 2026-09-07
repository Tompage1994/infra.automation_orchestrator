#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for the workflow resource.

Workflows don't fit the generic present/absent/exists CRUD state machine:
saving a new ``workflow_definition`` creates a version (with optimistic
concurrency via ``expected_version``), publishing/unpublishing are separate
POSTs, and the definition can reference other resources (credentials,
integrations, projects, LLM models) by name instead of UUID. This overrides
:meth:`run` entirely.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError

from ansible_collections.infra.automation_orchestrator.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.utils import guard_builtin, values_equal


def _current_definition(existing):
    version = (existing or {}).get("version") or {}
    return version.get("workflow_definition") or {}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError(f"Could not load DOCUMENTATION for {self.MODULE_NAME} module")
            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            params = validated_input.validated_parameters

            client = self._get_client(task_vars)
            name = params["name"]
            state = params.get("state", "present")
            allow_builtin = bool(params.get("allow_builtin", False))
            check_mode = self._task.check_mode

            existing = client.find_by_name("/api/v1/workflows", name)
            if existing:
                existing = client.direct_request("GET", f"/api/v1/workflows/{existing['id']}")

            if state == "exists":
                result.update(
                    {"changed": False, "failed": False, "exists": bool(existing), "workflow": existing or {}, "id": (existing or {}).get("id")}
                )
                return result

            if state == "absent":
                if not existing:
                    result.update({"changed": False, "failed": False, "workflow": {"state": "absent"}})
                    return result
                guard_message = guard_builtin(existing, allow_builtin)
                if guard_message:
                    result.update({"changed": False, "failed": True, "msg": guard_message})
                    return result
                if check_mode:
                    result.update({"changed": True, "failed": False, "workflow": {"state": "absent"}, "id": existing["id"]})
                    return result
                client.direct_request("DELETE", f"/api/v1/workflows/{existing['id']}")
                result.update({"changed": True, "failed": False, "workflow": {"state": "absent"}, "id": existing["id"]})
                return result

            # ---- state: present ----
            if existing:
                guard_message = guard_builtin(existing, allow_builtin)
                if guard_message:
                    result.update({"changed": False, "failed": True, "msg": guard_message})
                    return result
            else:
                if not params.get("project"):
                    raise AnsibleError("project is required when creating a workflow")
                if params.get("workflow_definition") is None:
                    raise AnsibleError("workflow_definition is required when creating a workflow")

            project_id = None
            if params.get("project"):
                project_id = client.resolve_id("/api/v1/projects", params["project"], what="project")

            definition = None
            if params.get("workflow_definition") is not None:
                definition = client.resolve_workflow_definition(params["workflow_definition"])
                if definition and not definition.get("name"):
                    definition["name"] = name
                if params.get("validate", True):
                    client.direct_request("POST", "/api/v1/workflows/validate", body={"workflow_definition": definition})

            desired = {"name": name}
            if project_id is not None:
                desired["project_id"] = project_id
            for key in ("description", "labels"):
                if params.get(key) is not None:
                    desired[key] = params[key]

            changed = False
            if not existing:
                create_body = dict(desired)
                if definition is not None:
                    create_body["workflow_definition"] = definition
                if check_mode:
                    result.update({"changed": True, "failed": False, "workflow": create_body, "id": None})
                    return result
                resource = client.direct_request("POST", "/api/v1/workflows", body=create_body)
                changed = True
            else:
                patch = {k: v for k, v in desired.items() if k != "project_id" and not values_equal(existing.get(k), v)}
                if definition is not None and not values_equal(definition, _current_definition(existing)):
                    patch["workflow_definition"] = definition
                    if params.get("change_description"):
                        patch["change_description"] = params["change_description"]
                    patch["expected_version"] = params.get("expected_version", existing.get("current_version"))
                if patch:
                    if check_mode:
                        result.update({"changed": True, "failed": False, "workflow": existing, "id": existing["id"]})
                        return result
                    resource = client.direct_request("PATCH", f"/api/v1/workflows/{existing['id']}", body=patch)
                    changed = True
                else:
                    resource = existing

            resource = client.direct_request("GET", f"/api/v1/workflows/{resource['id']}")

            published = params.get("published")
            if published is True and resource.get("published_version_number") != resource.get("current_version"):
                if not check_mode:
                    client.direct_request("POST", f"/api/v1/workflows/{resource['id']}/versions/{resource['current_version']}/publish", body={})
                    resource = client.direct_request("GET", f"/api/v1/workflows/{resource['id']}")
                changed = True
            elif published is False and resource.get("published_version_number") is not None:
                if not check_mode:
                    client.direct_request("POST", f"/api/v1/workflows/{resource['id']}/unpublish")
                    resource = client.direct_request("GET", f"/api/v1/workflows/{resource['id']}")
                changed = True

            result.update({"changed": changed, "failed": False, "workflow": resource, "id": resource.get("id")})

        except Exception as exc:  # noqa: BLE001 - action plugins must return, never raise, to Ansible
            import traceback as _tb

            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
