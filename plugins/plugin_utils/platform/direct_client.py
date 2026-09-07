# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Direct HTTP client for the Automation Orchestrator API.

Merges patterns from both predecessor collections:
- HTTP transport via ``ansible.module_utils.urls.Request`` and the
  create/update/delete/find dispatch shape from ``ansible.platform``'s
  ``DirectHTTPClient``.
- Three auth methods (password, token, OAuth2 client_credentials), token
  refresh with expiry tracking, and 401 retry-once from ``lennysh.ao_configuration``'s
  ``AoAPI``.
- ``wait_on_execution`` polling from ``infra.automation_orchestrator``'s
  (Tom's) ``OrchestratorModule``.

AO-specific differences from ``ansible.platform``: base path is always
``/api/v1``, list responses use a ``resources`` envelope (not ``results``),
exact-match filtering uses ``field[eq]=value``, and resource ids are UUID
strings rather than integers.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import logging
import threading
import time
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from ansible.module_utils.six.moves.http_cookiejar import CookieJar
from ansible.module_utils.six.moves.urllib.error import HTTPError
from ansible.module_utils.urls import ConnectionError as AnsibleConnectionError
from ansible.module_utils.urls import Request, SSLValidationError

from .base_client import BaseAPIClient
from .config import AOConfig
from .exceptions import AOError, APIError, AuthenticationError, TimeoutError as AOTimeoutError
from .types import TransformContext
from .utils import ID_TO_COLLECTION, is_uuid, walk_rewrite

logger = logging.getLogger(__name__)

_TERMINAL_EXECUTION_STATUSES = frozenset(("completed", "completed_with_errors", "failed", "cancelled"))


class AODirectClient(BaseAPIClient):
    """Direct HTTP client for the Automation Orchestrator API (single connection mode)."""

    def __init__(self, config: AOConfig):
        super().__init__(config)

        self.username = config.username
        self.password = config.password
        self.client_id = config.client_id
        self.client_secret = config.client_secret

        self._token = config.token
        self._token_expires_at: Optional[float] = 0 if config.token else None

        self.session = Request(cookies=CookieJar(), validate_certs=self.verify_ssl, timeout=self.request_timeout)
        self.session.headers.update({"User-Agent": "infra.automation_orchestrator", "Accept": "application/json"})

        self.api_version = "1"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # BaseAPIClient interface
    # ------------------------------------------------------------------

    def _detect_api_version(self) -> str:
        return "1"

    def _authenticate(self) -> None:
        self.ensure_auth()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _set_token(self, payload: dict) -> None:
        self._token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 900)
        self._token_expires_at = time.time() + max(expires_in - 30, 1)

    def _login_password(self) -> None:
        payload = self._raw_request(
            "POST",
            "/api/v1/auth/login",
            body={"username": self.username, "password": self.password},
            authenticate=False,
        )
        self._set_token(payload or {})

    def _login_client_credentials(self) -> None:
        payload = self._raw_request(
            "POST",
            "/api/v1/auth/token",
            form={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
            authenticate=False,
        )
        self._set_token(payload or {})

    def _refresh_token(self) -> None:
        payload = self._raw_request("POST", "/api/v1/auth/refresh", authenticate=False)
        self._set_token(payload or {})

    def ensure_auth(self) -> None:
        """Authenticate if needed, refreshing an expiring token before re-authenticating."""
        with self._lock:
            if self._token and (self._token_expires_at is None or time.time() < self._token_expires_at):
                return
            if self._token and self._token_expires_at:
                try:
                    self._refresh_token()
                    return
                except AOError:
                    self._token = None
            if self.client_id and self.client_secret:
                self._login_client_credentials()
                return
            if self.username and self.password:
                self._login_password()
                return
            if self._token:
                return
            raise AuthenticationError("No Automation Orchestrator credentials were provided", operation="authenticate")

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    def _build_url(self, path: str, query: Optional[Dict[str, Any]] = None) -> str:
        if path.startswith(("http://", "https://")):
            url = path
        else:
            if not path.startswith("/"):
                path = f"/{path}"
            url = f"{self.base_url}{path}"
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered, doseq=True)}"
        return url

    def _raw_request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        form: Optional[dict] = None,
        query: Optional[dict] = None,
        authenticate: bool = True,
        _retry: bool = True,
    ):
        """Make an authenticated request and return the parsed JSON body (or None)."""
        if authenticate:
            self.ensure_auth()

        url = self._build_url(path, query)
        headers = {"Accept": "application/json"}
        data = None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(form)
        elif body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body)
        if authenticate and self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            response = self.session.open(
                method.upper(),
                url,
                data=data,
                headers=headers,
                timeout=self.request_timeout,
                validate_certs=self.verify_ssl,
                follow_redirects=True,
            )
            raw = response.read()
            if not raw:
                return None
            try:
                return json.loads(raw)
            except ValueError:
                return {"_raw": raw.decode("utf-8", "replace")}
        except HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw) if raw else {}
            except ValueError:
                parsed = {"detail": raw.decode("utf-8", "replace") if raw else str(exc)}

            if exc.code == 401 and authenticate and _retry:
                self._token = None
                self._token_expires_at = 0
                try:
                    self.ensure_auth()
                except AuthenticationError:
                    raise AuthenticationError(
                        message=parsed.get("detail") or parsed.get("title") or "Unauthorized",
                        operation="request",
                        details={"status_code": 401, "path": path},
                    )
                return self._raw_request(method, path, body=body, form=form, query=query, authenticate=authenticate, _retry=False)

            message = parsed.get("detail") or parsed.get("title") or str(exc)
            raise APIError(message=message, operation="request", details={"path": path}, status_code=exc.code, response_body=parsed)
        except SSLValidationError as exc:
            raise AOError(f"SSL validation error for {url}: {exc}", operation="request") from exc
        except AnsibleConnectionError as exc:
            raise AOError(f"Connection error for {url}: {exc}", operation="request") from exc

    def direct_request(self, method: str, path: str, body: Optional[dict] = None, query: Optional[dict] = None) -> Any:
        """Make a raw authenticated request. Used by action plugins for non-CRUD endpoints."""
        return self._raw_request(method, path, body=body, query=query)

    # ------------------------------------------------------------------
    # Listing / lookup helpers
    # ------------------------------------------------------------------

    def list_all(self, path: str, query: Optional[dict] = None) -> list:
        """Follow cursor pagination and return every resource at path."""
        query = dict(query or {})
        resources = []
        cursor = None
        while True:
            page_query = dict(query)
            page_query["limit"] = min(int(page_query.get("limit") or 100), 100)
            if cursor:
                page_query["cursor"] = cursor
            payload = self._raw_request("GET", path, query=page_query) or {}
            if isinstance(payload, list):
                return payload
            chunk = payload.get("resources") or payload.get("results") or []
            resources.extend(chunk)
            cursor = payload.get("next")
            if not cursor:
                break
        return resources

    def find_by_name(self, path: str, name: Optional[str], name_field: str = "name") -> Optional[dict]:
        """Resolve a resource by UUID (direct GET) or by name (filter, with list-and-filter fallback).

        AO's ``field[eq]=`` filter is undocumented and not honored by every
        endpoint, so a full listing is used as a fallback when the filtered
        query returns nothing.
        """
        if name is None:
            return None
        if is_uuid(str(name)):
            return self._raw_request("GET", f"{path.rstrip('/')}/{name}")

        matches = []
        try:
            listed = self.list_all(path, {f"{name_field}[eq]": name})
        except AOError:
            listed = []
        for item in listed:
            if item.get(name_field) == name or item.get("name") == name:
                matches.append(item)
        if not matches:
            for item in self.list_all(path):
                if item.get(name_field) == name or item.get("name") == name:
                    matches.append(item)
        if len(matches) > 1:
            raise AOError(f"Multiple objects named {name!r} found at {path}", operation="find")
        return matches[0] if matches else None

    def resolve_id(self, path: str, name_or_id: Optional[str], name_field: str = "name", required: bool = True, what: Optional[str] = None) -> Optional[str]:
        if name_or_id in (None, ""):
            if required:
                raise AOError(f"A {what or path} name or ID is required", operation="resolve")
            return None
        if is_uuid(str(name_or_id)):
            return str(name_or_id)
        cache_key = (path, name_field, name_or_id)
        if cache_key in self.cache:
            return self.cache[cache_key]
        found = self.find_by_name(path, name_or_id, name_field=name_field)
        if not found:
            if required:
                raise AOError(f"{what or path} {name_or_id!r} was not found", operation="resolve")
            return None
        self.cache[cache_key] = found["id"]
        return found["id"]

    def resolve_name(self, path: str, object_id: Optional[str], name_field: str = "name") -> Optional[str]:
        if not object_id:
            return None
        if not is_uuid(str(object_id)):
            return object_id
        cache_key = ("name", path, object_id)
        if cache_key in self.cache:
            return self.cache[cache_key]
        try:
            obj = self._raw_request("GET", f"{path.rstrip('/')}/{object_id}")
        except AOError:
            return object_id
        name = (obj or {}).get(name_field) or (obj or {}).get("name") or object_id
        self.cache[cache_key] = name
        return name

    def resolve_llm_model_id(self, name_or_id: Optional[str]) -> Optional[str]:
        if name_or_id in (None, ""):
            return None
        if is_uuid(str(name_or_id)):
            return str(name_or_id)
        for integration in self.list_all("/api/v1/integrations"):
            try:
                models = self.list_all(f"/api/v1/integrations/{integration['id']}/models")
            except AOError:
                continue
            for model in models:
                if name_or_id in (model.get("name"), model.get("model_id"), model.get("id")):
                    return model["id"]
        raise AOError(f"LLM model {name_or_id!r} was not found", operation="resolve")

    def resolve_llm_model_name(self, model_id: Optional[str]) -> Optional[str]:
        if not model_id or not is_uuid(str(model_id)):
            return model_id
        for integration in self.list_all("/api/v1/integrations"):
            try:
                models = self.list_all(f"/api/v1/integrations/{integration['id']}/models")
            except AOError:
                continue
            for model in models:
                if model.get("id") == model_id:
                    return model.get("name") or model.get("model_id") or model_id
        return model_id

    # ------------------------------------------------------------------
    # Workflow definition name/id rewriting
    # ------------------------------------------------------------------

    def _rewriter(self, id_key: str, value: Any) -> Any:
        if value in (None, ""):
            return value
        if id_key == "llm_model_id":
            return self.resolve_llm_model_id(value)
        path, field = ID_TO_COLLECTION[id_key]
        return self.resolve_id(path, value, name_field=field, what=id_key)

    def _namer(self, id_key: str, value: Any) -> Any:
        if value in (None, ""):
            return value
        if id_key == "llm_model_id":
            return self.resolve_llm_model_name(value)
        path, field = ID_TO_COLLECTION[id_key]
        return self.resolve_name(path, value, name_field=field)

    def resolve_workflow_definition(self, definition: Optional[dict]) -> Optional[dict]:
        """Rewrite human-readable names inside a workflow definition to UUIDs (import direction)."""
        if not definition:
            return definition
        return walk_rewrite(deepcopy(definition), self._rewriter)

    def names_workflow_definition(self, definition: Optional[dict]) -> Optional[dict]:
        """Rewrite UUIDs inside a workflow definition back to human-readable names (export direction)."""
        if not definition:
            return definition
        return walk_rewrite(deepcopy(definition), self._namer)

    # ------------------------------------------------------------------
    # Execution polling
    # ------------------------------------------------------------------

    def wait_on_execution(self, execution_id: str, timeout: float = 300, interval: float = 2) -> dict:
        """Poll GET /executions/{id} until it reaches a terminal status.

        Raises:
            AOTimeoutError: if ``timeout`` elapses before a terminal status is reached.
            AOError: if the execution finishes as 'failed' or 'completed_with_errors'.
        """
        start = time.time()
        current_interval = interval
        while True:
            execution = self._raw_request("GET", f"/api/v1/executions/{execution_id}") or {}
            status = execution.get("status")

            if status in _TERMINAL_EXECUTION_STATUSES:
                if status in ("failed", "completed_with_errors"):
                    raise AOError(f"Execution {execution_id} finished with status {status}", operation="wait", details={"execution": execution})
                return execution

            if timeout and time.time() - start > timeout:
                raise AOTimeoutError(f"Monitoring of execution {execution_id} aborted after {timeout}s", operation="wait", timeout_seconds=timeout)

            time.sleep(current_interval)
            current_interval = min(current_interval * 1.5, 30)

    # ------------------------------------------------------------------
    # Generic CRUD dispatch (used by the base action plugin)
    # ------------------------------------------------------------------

    def execute(self, operation: str, module_name: str, ansible_data_dict: Optional[dict] = None, **kwargs) -> dict:
        if ansible_data_dict is None and "ansible_data" in kwargs:
            ansible_data_dict = kwargs.get("ansible_data")
        if is_dataclass(ansible_data_dict):
            ansible_data_dict = asdict(ansible_data_dict)
        ansible_data_dict = dict(ansible_data_dict or {})

        AnsibleClass, _APIClass, MixinClass = self.loader.load_classes_for_module(module_name, self.api_version)
        ansible_instance = AnsibleClass(**ansible_data_dict)

        context = TransformContext(client=self, cache=self.cache, api_version=self.api_version, operation=operation)

        if operation == "create":
            return self._create_resource(ansible_instance, MixinClass, context)
        if operation == "update":
            return self._update_resource(ansible_instance, MixinClass, context)
        if operation == "delete":
            return self._delete_resource(ansible_instance, MixinClass, context)
        if operation == "find":
            return self._find_resource(ansible_instance, MixinClass, context)
        raise ValueError(f"Unknown operation: {operation}")

    def _create_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        api_data = mixin_class.from_ansible_data(ansible_data, context)
        operations = mixin_class.get_endpoint_operations()
        api_result = self._execute_operations(operations, api_data, context, required_for="create")
        ansible_instance = mixin_class.from_api(api_result, context)
        result = asdict(ansible_instance)
        result["changed"] = True
        return result

    def _update_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        resource_id = getattr(ansible_data, "id", None)
        if not resource_id and not getattr(mixin_class, "is_singleton", False):
            raise ValueError("Resource ID required for update operation")

        api_data = mixin_class.from_ansible_data(ansible_data, context)
        operations = mixin_class.get_endpoint_operations()
        api_result = self._execute_operations(operations, api_data, context, required_for="update")
        ansible_instance = mixin_class.from_api(api_result, context)
        result = asdict(ansible_instance)
        result["changed"] = True
        return result

    def _delete_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        resource_id = getattr(ansible_data, "id", None)
        if not resource_id:
            raise ValueError("Resource ID required for delete operation")

        operations = mixin_class.get_endpoint_operations()
        delete_op = operations.get("delete")
        if not delete_op:
            raise ValueError(f"Delete operation not defined for {mixin_class.__name__}")

        path = delete_op.path.format(id=resource_id)
        self._raw_request(delete_op.method, path)
        return {"changed": True, "deleted": True}

    def _find_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        operations = mixin_class.get_endpoint_operations()
        get_op = operations.get("get")
        list_op = operations.get("list")

        if getattr(mixin_class, "is_singleton", False):
            if not get_op:
                raise ValueError(f"No GET operation defined for singleton {mixin_class.__name__}")
            api_result = self._raw_request(get_op.method, get_op.path) or {}
            return asdict(mixin_class.from_api(api_result, context))

        if not list_op:
            raise ValueError(f"List operation not defined for {mixin_class.__name__}")

        lookup_field = mixin_class.get_lookup_field()
        lookup_value = getattr(ansible_data, lookup_field, None)

        composite_params: Dict[str, Any] = {}
        if hasattr(mixin_class, "get_find_list_query_params"):
            api_data_for_find = mixin_class.from_ansible_data(ansible_data, context)
            composite_params = mixin_class.get_find_list_query_params(api_data_for_find) or {}

        # ID-based direct lookup when the lookup value is itself a UUID.
        if get_op and lookup_value is not None and is_uuid(str(lookup_value)):
            api_result = self._raw_request(get_op.method, get_op.path.format(id=lookup_value)) or {}
            if api_result.get("id"):
                for param_key, param_val in composite_params.items():
                    if str(api_result.get(param_key)) != str(param_val):
                        raise ValueError(f"Resource {lookup_value} found but composite key constraints {composite_params} do not match")
                return asdict(mixin_class.from_api(api_result, context))

        if not lookup_value and not composite_params:
            raise ValueError(f"Lookup field '{lookup_field}' not found in data")

        query_params: Dict[str, Any] = dict(composite_params)
        if lookup_value:
            query_params[f"{lookup_field}[eq]"] = lookup_value
        resources = self._list_page(list_op.path, query_params)

        # AO's `field[eq]=` filter is undocumented and not honored by every
        # endpoint; fall back to a full listing filtered client-side.
        if not resources and lookup_value:
            all_resources = self.list_all(list_op.path, composite_params or None)
            resources = [r for r in all_resources if r.get(lookup_field) == lookup_value]

        if resources:
            return asdict(mixin_class.from_api(resources[0], context))

        raise ValueError(f"Resource not found: {lookup_field}={lookup_value}")

    def _list_page(self, path: str, query: Optional[dict] = None) -> list:
        payload = self._raw_request("GET", path, query=query) or {}
        if isinstance(payload, list):
            return payload
        return payload.get("resources") or payload.get("results") or []

    def _execute_operations(self, operations: Dict[str, Any], api_data: Any, context: TransformContext, required_for: Optional[str] = None) -> dict:
        """Execute one or more endpoint operations, in order, propagating the created id."""
        results: Dict[str, Any] = {}
        relevant_ops = {name: op for name, op in operations.items() if op.required_for == required_for or required_for is None}
        sorted_ops = sorted(relevant_ops.items(), key=lambda item: item[1].order)

        for op_name, endpoint_op in sorted_ops:
            if endpoint_op.depends_on and endpoint_op.depends_on not in results:
                continue

            path = endpoint_op.path
            if endpoint_op.path_params:
                for param in endpoint_op.path_params:
                    param_value = results.get("id") or getattr(api_data, "id", None)
                    if param_value:
                        path = path.replace(f"{{{param}}}", str(param_value))

            request_data: Dict[str, Any] = {}
            if endpoint_op.fields:
                for field_name in endpoint_op.fields:
                    value = getattr(api_data, field_name, None)
                    if value is None:
                        continue
                    request_data[field_name] = value

            if endpoint_op.flatten_body and len(request_data) == 1:
                request_data = next(iter(request_data.values()))

            if endpoint_op.depends_on and not request_data:
                continue

            body = request_data if endpoint_op.method != "GET" else None
            query = request_data if endpoint_op.method == "GET" else None
            result_data = self._raw_request(endpoint_op.method, path, body=body, query=query) or {}
            results[op_name] = result_data
            if isinstance(result_data, dict) and "id" in result_data and "id" not in results:
                results["id"] = result_data["id"]

        return results.get("create") or results.get("update") or results.get("get") or results
