#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Base action plugin for Automation Orchestrator resources.

Adapted from ``ansible.platform``'s ``BaseResourceActionPlugin`` with two
deliberate simplifications: there is no connection plugin / persistent
manager subprocess (AO is a single HTTP service, so the action plugin talks
to :class:`AODirectClient` directly), and the state machine only supports
``present`` / ``absent`` / ``exists`` (no ``enforced``).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib
import importlib.util
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import yaml
from ansible.errors import AnsibleError
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display

from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.config import extract_ao_config
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.direct_client import AODirectClient
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.utils import guard_builtin

display = Display()


class BaseResourceActionPlugin(ActionBase):
    """Base action plugin for all Automation Orchestrator resources.

    Subclasses that set ``MODULE_NAME`` and ``MODEL_CLASS`` get full CRUD
    idempotency for free (see :meth:`run`). Override the extension hooks
    below to customise behaviour without duplicating the pipeline.

    Example (simple resource)::

        class ActionModule(BaseResourceActionPlugin):
            MODULE_NAME = "project"
            MODEL_CLASS = AnsibleProject
    """

    # Action plugins here always target localhost — the AO API is remote HTTP,
    # the "connection" is always local.
    _supports_async = False

    MODULE_NAME: Optional[str] = None
    MODEL_CLASS: Optional[type] = None
    LOOKUP_FIELD = "name"

    # Fields sent to the API as operation directives but never returned by
    # GET/LIST responses (so they must be excluded from idempotency checks).
    _WRITE_ONLY_FIELDS: frozenset = frozenset()
    # API-generated fields returned flat only (not part of the nested resource dict).
    _EXTRA_RETURN_FIELDS: frozenset = frozenset()
    # FK fields whose values can change via update (suppresses the name/id-mismatch skip
    # in _should_update so a real rename is detected).
    _MUTABLE_FK_FIELDS: frozenset = frozenset()
    # If True, run() refuses to create/update/delete an existing resource with
    # is_builtin=true unless the module's allow_builtin=true.
    _GUARD_BUILTIN = False

    _AUTH_PARAMS = frozenset(
        {
            "ao_host",
            "ao_username",
            "ao_password",
            "ao_token",
            "ao_client_id",
            "ao_client_secret",
            "ao_validate_certs",
            "ao_request_timeout",
            "ao_config_file",
        }
    )
    _ANSIBLE_DIRECTIVES = frozenset({"state"})
    _READ_ONLY_FIELDS = frozenset({"id", "created_at", "updated_at", "url"})

    # ------------------------------------------------------------------
    # Subclass extension hooks
    # ------------------------------------------------------------------

    def _resolve_lookup(self, resource: Any, resource_data: dict, validated_params: dict) -> None:
        """Called after MODEL_CLASS is instantiated. Override to mutate resource/resource_data. Default: no-op."""

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build the ansible_data dict passed to client.execute(). Default: every dataclass field."""
        return asdict(resource)

    def _pre_execute_hook(self, ansible_data: dict, write_only_data: dict, validated_params: dict, operation: str) -> None:
        """Called immediately before client.execute(). Override to mutate ansible_data in place. Default: no-op."""

    # ------------------------------------------------------------------
    # Client construction
    # ------------------------------------------------------------------

    def _get_client(self, task_vars: dict) -> AODirectClient:
        config = extract_ao_config(task_args=self._task.args, host_vars=task_vars, required=True)
        return AODirectClient(config)

    # ------------------------------------------------------------------
    # Documentation / argspec
    # ------------------------------------------------------------------

    def _get_documentation(self) -> str:
        if not self.MODULE_NAME:
            return ""
        parent_pkg = type(self).__module__.rsplit(".", 2)[0]  # ...plugins
        for candidate in (
            f"{parent_pkg}.modules.{self.MODULE_NAME}",
            f"ansible_collections.infra.automation_orchestrator.plugins.modules.{self.MODULE_NAME}",
        ):
            try:
                mod = importlib.import_module(candidate)
                doc = getattr(mod, "DOCUMENTATION", None)
                if doc:
                    return doc
            except (ImportError, ModuleNotFoundError):
                continue
        return ""

    def _build_argspec_from_docs(self, documentation: str) -> dict:
        try:
            doc_data = yaml.safe_load(documentation)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse DOCUMENTATION: {exc}") from exc

        options = {}
        extends_fragments = doc_data.get("extends_documentation_fragment", [])
        if not isinstance(extends_fragments, list):
            extends_fragments = [extends_fragments]
        for fragment_name in extends_fragments:
            fragment_options = self._load_documentation_fragment(fragment_name)
            if fragment_options:
                options.update(fragment_options)
        options.update(doc_data.get("options", {}))

        return {
            "argument_spec": options,
            "mutually_exclusive": doc_data.get("mutually_exclusive", []),
            "required_together": doc_data.get("required_together", []),
            "required_one_of": doc_data.get("required_one_of", []),
            "required_if": doc_data.get("required_if", []),
        }

    def _load_documentation_fragment(self, fragment_name: str) -> dict:
        try:
            fragment = fragment_name.split(".")[-1] if "." in fragment_name else fragment_name
            fragment_path = Path(__file__).parent.parent / "doc_fragments" / f"{fragment}.py"
            if not fragment_path.exists():
                self._display.vvvv(f"Documentation fragment '{fragment_name}' not found, skipping")
                return {}

            spec = importlib.util.spec_from_file_location(f"doc_fragment_{fragment}", fragment_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            fragment_class = getattr(module, "ModuleDocFragment", None)
            if fragment_class is None:
                return {}
            fragment_doc = getattr(fragment_class, "DOCUMENTATION", "")
            if not fragment_doc:
                return {}
            return yaml.safe_load(fragment_doc).get("options", {})
        except Exception as exc:  # noqa: BLE001 - fragment loading is best-effort
            self._display.warning(f"Failed to load documentation fragment '{fragment_name}': {exc}")
            return {}

    def _validate_data(self, data: dict, argspec: dict, direction: str) -> Any:
        arg_spec_dict = argspec.get("argument_spec", {})
        for param, spec in arg_spec_dict.items():
            if spec.get("type") in ("float", "int") and data.get(param) == "":
                data.pop(param, None)

        validator = ArgumentSpecValidator(
            argument_spec=arg_spec_dict,
            mutually_exclusive=argspec.get("mutually_exclusive"),
            required_together=argspec.get("required_together"),
            required_one_of=argspec.get("required_one_of"),
            required_if=argspec.get("required_if"),
        )
        result = validator.validate(data)
        if result.error_messages:
            raise AnsibleError(f"{direction.title()} validation failed: " + ", ".join(result.error_messages))
        return result

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Return True if any explicitly-provided writable field differs between desired and current.

        Only fields present in both dicts are compared. Auth params, state
        directives, read-only fields, and write-only fields are excluded.
        FK fields where desired is a name (non-UUID str) and current is a
        UUID string are skipped unless listed in _MUTABLE_FK_FIELDS.
        """
        skip_keys = self._AUTH_PARAMS | self._ANSIBLE_DIRECTIVES | self._READ_ONLY_FIELDS | self._WRITE_ONLY_FIELDS
        from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.utils import is_uuid

        for key, desired_val in desired_data.items():
            if key in skip_keys or desired_val is None:
                continue
            if key not in current_data:
                continue
            current_val = current_data[key]
            if (
                key not in self._MUTABLE_FK_FIELDS
                and isinstance(desired_val, str)
                and isinstance(current_val, str)
                and not is_uuid(desired_val)
                and is_uuid(current_val)
            ):
                continue
            if type(desired_val) is type(current_val):
                if desired_val != current_val:
                    return True
            elif str(desired_val) != str(current_val):
                return True
        return False

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """State machine: present -> find/update/create, absent -> find/delete, exists -> find only."""
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        if self.MODEL_CLASS is None:
            raise AnsibleError(f"{type(self).__name__} must set MODEL_CLASS or override run()")

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError(f"Could not load DOCUMENTATION for {self.MODULE_NAME} module")
            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            validated_params = validated_input.validated_parameters

            client = self._get_client(task_vars)
            self._client = client

            resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS}
            write_only_data = {f: resource_data.pop(f) for f in self._WRITE_ONLY_FIELDS if f in resource_data}

            resource = self.MODEL_CLASS(**{k: v for k, v in resource_data.items() if k in self.MODEL_CLASS.__dataclass_fields__})
            self._resolve_lookup(resource, resource_data, validated_params)

            state = validated_params.get("state", "present")
            lookup_val = getattr(resource, self.LOOKUP_FIELD, None)

            # ---- state: exists (read-only) ----
            if state == "exists":
                try:
                    find_result = client.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=asdict(resource))
                    exists = bool(find_result and find_result.get("id"))
                except Exception:
                    find_result, exists = {}, False
                result.update(
                    {
                        "changed": False,
                        "failed": False,
                        "exists": exists,
                        self.MODULE_NAME: find_result if exists else {},
                        "id": find_result.get("id") if exists else None,
                    }
                )
                return result

            # ---- find existing resource (used by both present and absent) ----
            find_result = None
            try:
                find_result = client.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=asdict(resource))
                if not (find_result and find_result.get("id")):
                    find_result = None
            except Exception:
                find_result = None

            self._existing = find_result

            if self._GUARD_BUILTIN and find_result is not None:
                guard_message = guard_builtin(find_result, bool(validated_params.get("allow_builtin")))
                if guard_message:
                    result.update({"changed": False, "failed": True, "msg": guard_message})
                    return result

            # ---- absent ----
            if state == "absent":
                if find_result is None:
                    result.update({"changed": False, "failed": False, self.MODULE_NAME: {"state": "absent"}})
                    return result
                if self._task.check_mode:
                    result.update({"changed": True, "failed": False, self.MODULE_NAME: {"state": "absent"}})
                    return result
                resource.id = find_result["id"]
                client.execute(operation="delete", module_name=self.MODULE_NAME, ansible_data=asdict(resource))
                result.update({"changed": True, "failed": False, self.MODULE_NAME: {"state": "absent"}, "id": find_result["id"]})
                return result

            # ---- present ----
            if find_result is not None:
                if not self._should_update(resource_data, find_result):
                    result.update({"changed": False, "failed": False, self.MODULE_NAME: find_result, "id": find_result.get("id")})
                    return result
                operation = "update"
                resource.id = find_result["id"]
            else:
                operation = "create"

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {self.LOOKUP_FIELD: lookup_val, "id": getattr(resource, "id", None)},
                    }
                )
                return result

            ansible_data = self._build_ansible_data(resource, validated_params, operation)
            self._pre_execute_hook(ansible_data, write_only_data, validated_params, operation)
            manager_result = client.execute(operation=operation, module_name=self.MODULE_NAME, ansible_data=ansible_data)

            argspec_fields = set(argspec.get("argument_spec", {}).keys())
            strip_from_resource = self._ANSIBLE_DIRECTIVES | (self._READ_ONLY_FIELDS - {"id"}) | {"changed"}
            filtered = {k: v for k, v in manager_result.items() if k in argspec_fields or k == "id"}
            validated_output = {k: v for k, v in filtered.items() if k not in strip_from_resource}

            extra_flat = {k: manager_result[k] for k in self._EXTRA_RETURN_FIELDS if k in manager_result and manager_result[k] is not None}

            result.update(
                {
                    "changed": manager_result.get("changed", False),
                    "failed": False,
                    self.MODULE_NAME: validated_output,
                    "id": validated_output.get("id"),
                    **extra_flat,
                }
            )

        except Exception as exc:  # noqa: BLE001 - action plugins must return, never raise, to Ansible
            import traceback as _tb

            self._display.vvv(f"Error in {self.MODULE_NAME} action plugin: {exc}")
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
