#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for launching a workflow execution.

Unlike the other resources in this collection, an execution is not a CRUD
resource with a natural idempotency key — launching one is an action, always
``changed``. This overrides :meth:`run` entirely instead of relying on
:class:`BaseResourceActionPlugin`'s present/absent/exists state machine, while
still reusing its documentation/argspec loading and client construction
helpers.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError

from ansible_collections.infra.automation_orchestrator.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.exceptions import AOError
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.utils import is_uuid


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "execution_launch"

    def _resolve_workflow_id(self, client, workflow, project):
        if is_uuid(workflow):
            return workflow

        query = {"name[eq]": workflow}
        project_id = None
        if project:
            project_id = client.resolve_id("/api/v1/projects", project, what="project")
            query["project_id[eq]"] = project_id

        matches = client.list_all("/api/v1/workflows", query)
        if not matches:
            # AO's name[eq] filter is undocumented and not honored by every
            # endpoint; fall back to a full listing filtered client-side.
            fallback_query = {"project_id[eq]": project_id} if project_id else None
            matches = [w for w in client.list_all("/api/v1/workflows", fallback_query) if w.get("name") == workflow]

        if not matches:
            raise AnsibleError(f"Workflow '{workflow}' was not found")
        if len(matches) > 1:
            raise AnsibleError(f"Multiple workflows named '{workflow}' were found; specify 'project' to disambiguate")
        return matches[0]["id"]

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        # Call ActionBase.run() directly - this action does not use the
        # present/absent/exists state machine from BaseResourceActionPlugin.run().
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
            workflow_id = self._resolve_workflow_id(client, params["workflow"], params.get("project"))

            if self._task.check_mode:
                result.update({"changed": True, "execution_id": None, "status": None, "execution": {}})
                return result

            launch_data = {
                "workflow_id": workflow_id,
                "trigger_node_id": params["trigger_node_id"],
                "input_data": params.get("input_data") or {},
                "use_published": bool(params.get("use_published", False)),
            }
            execution = client.direct_request("POST", "/api/v1/executions", body=launch_data)

            result.update(
                {
                    "changed": True,
                    "failed": False,
                    "execution_id": execution.get("id"),
                    "status": execution.get("status"),
                    "execution": execution,
                }
            )

            if params.get("wait"):
                try:
                    execution = client.wait_on_execution(
                        execution["id"],
                        timeout=params.get("timeout", 300),
                        interval=params.get("interval", 2),
                    )
                    result["execution"] = execution
                    result["status"] = execution.get("status")
                except AOError as exc:
                    result.update({"failed": True, "msg": str(exc), "status": exc.details.get("execution", {}).get("status")})
                    result["execution"] = exc.details.get("execution", result["execution"])

        except Exception as exc:  # noqa: BLE001 - action plugins must return, never raise, to Ansible
            import traceback as _tb

            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
