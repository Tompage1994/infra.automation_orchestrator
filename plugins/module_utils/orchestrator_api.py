from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re
import time
from json import dumps, loads
from os import access, environ, getcwd, R_OK
from os.path import expanduser, isfile, join, split
from socket import getaddrinfo, IPPROTO_TCP
from uuid import UUID

from ansible.module_utils.basic import AnsibleModule, env_fallback
from ansible.module_utils.urls import ConnectionError, Request, SSLValidationError
from ansible.module_utils.six.moves.urllib.error import HTTPError
from ansible.module_utils.six.moves.urllib.parse import quote, urlencode, urlparse

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

_COLLECTION_VERSION = "0.0.1"
_API_PREFIX = "/api/v1"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_TERMINAL_EXECUTION_STATUSES = frozenset(
    ("completed", "completed_with_errors", "failed", "cancelled")
)


class ConfigFileException(Exception):
    pass


class OrchestratorModule(AnsibleModule):
    url = None
    AUTH_ARGSPEC = dict(
        orchestrator_host=dict(
            required=False,
            aliases=["ao_host"],
            fallback=(env_fallback, ["AO_HOST"]),
        ),
        orchestrator_username=dict(
            required=False,
            aliases=["ao_username"],
            fallback=(env_fallback, ["AO_USERNAME"]),
        ),
        orchestrator_password=dict(
            no_log=True,
            aliases=["ao_password"],
            required=False,
            fallback=(env_fallback, ["AO_PASSWORD"]),
        ),
        orchestrator_token=dict(
            type="raw",
            no_log=True,
            aliases=["ao_token", "access_token"],
            required=False,
            fallback=(env_fallback, ["AO_TOKEN"]),
        ),
        validate_certs=dict(
            type="bool",
            aliases=["ao_validate_certs"],
            required=False,
            default=True,
            fallback=(env_fallback, ["AO_VALIDATE_CERTS"]),
        ),
        request_timeout=dict(
            type="float",
            aliases=["ao_request_timeout"],
            required=False,
            default=30,
            fallback=(env_fallback, ["AO_REQUEST_TIMEOUT"]),
        ),
        orchestrator_config_file=dict(
            type="path",
            aliases=["ao_config_file"],
            required=False,
            default=None,
        ),
    )
    short_params = {
        "host": "orchestrator_host",
        "username": "orchestrator_username",
        "password": "orchestrator_password",
        "verify_ssl": "validate_certs",
        "request_timeout": "request_timeout",
        "token": "orchestrator_token",
    }
    host = None
    username = None
    password = None
    token = None
    verify_ssl = True
    request_timeout = 30
    authenticated = False
    config_name = ".ao_cli.cfg"
    version_checked = False
    error_callback = None
    warn_callback = None

    def __init__(self, argument_spec=None, direct_params=None, error_callback=None, warn_callback=None, **kwargs):
        full_argspec = {}
        full_argspec.update(OrchestratorModule.AUTH_ARGSPEC)
        if argument_spec:
            full_argspec.update(argument_spec)
        kwargs["supports_check_mode"] = True

        self.error_callback = error_callback
        self.warn_callback = warn_callback
        self.json_output = {"changed": False}
        self.update_secrets = False

        if direct_params is not None:
            self.params = direct_params
            self.cleanup_files = []
            self._diff = False
            self._debug = False
            self._verbosity = 0
            self.check_mode = kwargs.get("check_mode", False)
            self._direct_params = True
        else:
            self._direct_params = False
            super().__init__(argument_spec=full_argspec, **kwargs)

        self.load_config_files()

        for short_param, long_param in self.short_params.items():
            direct_value = self.params.get(long_param)
            if direct_value is not None:
                setattr(self, short_param, direct_value)

        self._parse_token()

        if not self.host:
            self.fail_json(msg="Missing required parameter orchestrator_host (or AO_HOST environment variable)")

        if not self.host.startswith(("https://", "http://")):
            self.host = "https://{0}".format(self.host)

        try:
            self.url = urlparse(self.host)
            self.url_prefix = self.url.path
        except Exception as exc:
            self.fail_json(msg="Unable to parse orchestrator_host as a URL ({0}): {1}".format(self.host, exc))

        try:
            proxy_env_var_name = "{0}_proxy".format(self.url.scheme)
            if not environ.get(proxy_env_var_name) and not environ.get(proxy_env_var_name.upper()):
                getaddrinfo(self.url.hostname, self.url.port, proto=IPPROTO_TCP)
        except Exception as exc:
            self.fail_json(msg="Unable to resolve orchestrator_host ({0}): {1}".format(self.url.hostname, exc))

        self.session = Request(unredirected_headers=["Authorization"])

    def fail_json(self, msg, **kwargs):
        if self._direct_params:
            if self.error_callback:
                self.error_callback(msg, **kwargs)
            raise SystemExit(1)
        super().fail_json(msg, **kwargs)

    def exit_json(self, **kwargs):
        if self._direct_params:
            self.json_output.update(kwargs)
            return self.json_output
        super().exit_json(**kwargs)

    def warn(self, warning):
        if self.warn_callback:
            self.warn_callback(warning)
        elif not self._direct_params:
            super().warn(warning)

    def _parse_token(self):
        if isinstance(self.token, dict):
            if "token" in self.token:
                self.token = self.token["token"]
            elif "access_token" in self.token:
                self.token = self.token["access_token"]
            else:
                self.fail_json(msg="The provided dict in orchestrator_token did not contain a token entry")

    def load_config_files(self):
        config_files = [
            "/etc/automation_orchestrator/ao_cli.cfg",
            join(expanduser("~"), self.config_name),
        ]
        local_dir = getcwd()
        config_files.append(join(local_dir, self.config_name))
        while split(local_dir)[1]:
            local_dir = split(local_dir)[0]
            config_files.append(join(local_dir, self.config_name))

        if self.params.get("orchestrator_config_file"):
            config_files.append(self.params["orchestrator_config_file"])

        for config_file in config_files:
            if isfile(config_file) and access(config_file, R_OK):
                self._load_config_file(config_file)

    def _load_config_file(self, config_file):
        if config_file.endswith((".yml", ".yaml")):
            if not HAS_YAML:
                raise ConfigFileException("PyYAML is required to read config file {0}".format(config_file))
            with open(config_file, "r") as config_handle:
                config_data = yaml.safe_load(config_handle) or {}
            for key, value in config_data.items():
                if key in self.short_params:
                    setattr(self, self.short_params[key], value)
                elif key in self.AUTH_ARGSPEC:
                    setattr(self, key.replace("orchestrator_", ""), value)
            return

        parser = __import__("configparser").ConfigParser()
        parser.read(config_file)
        for section in parser.sections():
            for option, value in parser.items(section):
                if option in self.short_params:
                    setattr(self, self.short_params[option], value)

    def build_url(self, endpoint, query_params=None):
        if not endpoint.startswith("/"):
            endpoint = "/{0}".format(endpoint)

        hostname_prefix = self.url_prefix.rstrip("/")
        if not endpoint.startswith(hostname_prefix + _API_PREFIX):
            endpoint = hostname_prefix + _API_PREFIX + endpoint

        url = self.url._replace(path=endpoint)
        if query_params:
            url = url._replace(query=urlencode(query_params, doseq=True))
        return url

    def authenticate(self):
        if self.authenticated:
            return

        if self.token:
            self.authenticated = True
            return

        if not (self.username and self.password):
            self.fail_json(
                msg="Authentication required. Provide orchestrator_token or orchestrator_username and orchestrator_password."
            )

        response = self.make_request(
            "POST",
            "auth/login",
            data={"username": self.username, "password": self.password},
            skip_auth=True,
        )
        if response["status_code"] != 200:
            self.fail_json(msg="Failed to authenticate", response=response)

        self.token = response["json"].get("access_token")
        if not self.token:
            self.fail_json(msg="Login response did not include access_token", response=response)

        self.authenticated = True

    def _get_authorization_header(self):
        if not self.authenticated:
            self.authenticate()
        return "Bearer {0}".format(self.token)

    def make_request(self, method, endpoint, data=None, headers=None, skip_auth=False):
        if not method:
            raise Exception("The HTTP method must be defined")

        query_params = None
        if method in ("GET", "DELETE", "HEAD"):
            query_params = data
            request_data = None
        else:
            request_data = data

        url = self.build_url(endpoint, query_params=query_params)
        headers = headers.copy() if headers else {}
        if not skip_auth:
            headers["Authorization"] = self._get_authorization_header()
        if method in ("POST", "PUT", "PATCH"):
            headers.setdefault("Content-Type", "application/json")

        payload = None
        if request_data is not None and headers.get("Content-Type", "") == "application/json":
            payload = dumps(request_data)

        try:
            response = self.session.open(
                method,
                url.geturl(),
                headers=headers,
                timeout=self.request_timeout,
                validate_certs=self.verify_ssl,
                follow_redirects=True,
                data=payload,
            )
        except SSLValidationError as ssl_err:
            self.fail_json(msg="Could not establish a secure connection to your host ({0}): {1}.".format(url.netloc, ssl_err))
        except ConnectionError as con_err:
            self.fail_json(msg="There was a network error trying to connect to your host ({0}): {1}.".format(url.netloc, con_err))
        except HTTPError as http_err:
            try:
                error_body = http_err.read()
            except (OSError, AttributeError, ValueError):
                error_body = b""
            if error_body:
                try:
                    error_json = loads(error_body)
                except ValueError:
                    error_json = error_body.decode("utf-8", errors="replace")
            else:
                error_json = {}
            detail = ""
            if isinstance(error_json, dict):
                detail = error_json.get("detail") or error_json.get("message") or ""
            elif error_json:
                detail = error_json
            msg = "Unexpected HTTP error from host ({0}): {1}.".format(url.netloc, http_err)
            if detail:
                msg = "{0} {1}".format(msg, detail)
            self.fail_json(msg=msg, status_code=getattr(http_err, "code", None), response=error_json)

        response_body = response.read()
        if response_body:
            try:
                response_json = loads(response_body)
            except ValueError:
                response_json = response_body.decode("utf-8", errors="replace")
        else:
            response_json = {}

        result = {"status_code": response.getcode(), "json": response_json}

        if not self.version_checked:
            self.version_checked = True

        if result["status_code"] == 401:
            self.fail_json(msg="Invalid Automation Orchestrator authentication credentials.", **result)
        if result["status_code"] == 403:
            detail = result["json"].get("detail", "Forbidden") if isinstance(result["json"], dict) else "Forbidden"
            self.fail_json(msg="You don't have permission to {0}: {1}".format(method, detail), **result)
        if result["status_code"] == 404:
            detail = result["json"].get("detail", "Not found") if isinstance(result["json"], dict) else "Not found"
            self.fail_json(msg="The requested object could not be found at {0}: {1}".format(endpoint, detail), **result)
        if result["status_code"] == 405:
            self.fail_json(msg="The Automation Orchestrator server says you can't make a request with the {0} method to this endpoint".format(method), **result)

        return result

    def get_endpoint(self, endpoint, **kwargs):
        return self.make_request("GET", endpoint, data=kwargs.get("data"))

    def post_endpoint(self, endpoint, **kwargs):
        if self.check_mode:
            self.json_output["changed"] = True
            self.exit_json(**self.json_output)
        return self.make_request("POST", endpoint, data=kwargs.get("data"))

    def patch_endpoint(self, endpoint, **kwargs):
        if self.check_mode:
            self.json_output["changed"] = True
            self.exit_json(**self.json_output)
        return self.make_request("PATCH", endpoint, data=kwargs.get("data"))

    def delete_endpoint(self, endpoint, **kwargs):
        if self.check_mode:
            self.json_output["changed"] = True
            self.exit_json(**self.json_output)
        return self.make_request("DELETE", endpoint, data=kwargs.get("data"))

    @staticmethod
    def is_uuid(value):
        if not isinstance(value, str):
            return False
        if _UUID_RE.match(value):
            return True
        try:
            UUID(value)
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    @staticmethod
    def item_path(endpoint, item_id):
        endpoint = endpoint.strip("/")
        return "{0}/{1}".format(endpoint, quote(str(item_id), safe=""))

    def get_all_endpoint(self, endpoint, max_items=10000, **query_params):
        params = dict(query_params)
        params.setdefault("limit", 100)
        resources = []
        while True:
            response = self.get_endpoint(endpoint, data=params)
            if response["status_code"] != 200:
                self.fail_json(msg="Failed to list resources from {0}".format(endpoint), response=response)

            page = response["json"]
            if "resources" not in page:
                self.fail_json(msg="Expected paginated list from API at {0}, got: {1}".format(endpoint, page))

            resources.extend(page["resources"])
            if len(resources) > max_items:
                self.fail_json(msg="The number of items being queried for is higher than {0}.".format(max_items))

            next_cursor = page.get("next")
            if not next_cursor:
                break
            params["cursor"] = next_cursor

        response["json"]["resources"] = resources
        response["json"]["next"] = None
        return response

    def get_one(self, endpoint, name_or_id=None, allow_none=True, check_exists=False, name_field="name", **filters):
        if name_or_id is not None and self.is_uuid(name_or_id):
            response = self.get_endpoint(self.item_path(endpoint, name_or_id))
            if response["status_code"] == 200:
                item = response["json"]
            elif allow_none:
                return None
            else:
                self.fail_json(msg="Resource not found at {0}/{1}".format(endpoint, name_or_id), response=response)
        else:
            query_params = dict(filters)
            if name_or_id is not None:
                query_params["{0}[eq]".format(name_field)] = name_or_id
            response = self.get_endpoint(endpoint, data=query_params)
            if response["status_code"] != 200:
                self.fail_json(msg="Failed to query {0}".format(endpoint), response=response)

            resources = response["json"].get("resources", [])
            if not resources:
                if allow_none:
                    return None
                self.fail_wanted_one(response, endpoint, query_params)
            if len(resources) > 1:
                if name_or_id is not None:
                    item = None
                    for resource in resources:
                        if str(resource.get("id")) == str(name_or_id):
                            item = resource
                            break
                        if resource.get(name_field) == name_or_id:
                            item = resource
                            break
                    if item is None:
                        self.fail_wanted_one(response, endpoint, query_params)
                else:
                    self.fail_wanted_one(response, endpoint, query_params)
            else:
                item = resources[0]

        if check_exists:
            self.json_output["id"] = item["id"]
            self.exit_json(**self.json_output)
        return item

    def fail_wanted_one(self, response, endpoint, query_params):
        resources = response["json"].get("resources", [])
        sample = resources[:2]
        if len(resources) > 2:
            sample.append("...more results snipped...")
        self.fail_json(
            msg="Request to {0} returned {1} items, expected 1".format(endpoint, len(resources)),
            query=query_params,
            response=sample,
            total_results=len(resources),
        )

    def get_exactly_one(self, endpoint, name_or_id=None, **kwargs):
        return self.get_one(endpoint, name_or_id=name_or_id, allow_none=False, **kwargs)

    def resolve_name_to_id(self, endpoint, name_or_id, **kwargs):
        return self.get_exactly_one(endpoint, name_or_id, **kwargs)["id"]

    def delete_if_needed(self, existing_item, endpoint, item_type=None, auto_exit=True):
        if not existing_item:
            if auto_exit:
                self.exit_json(**self.json_output)
            return self.json_output

        item_id = existing_item.get("id")
        item_name = existing_item.get("name", item_id)
        if not item_type:
            item_type = endpoint.strip("/").split("/")[-1]

        response = self.delete_endpoint(self.item_path(endpoint, item_id))
        if response["status_code"] in (200, 202, 204):
            self.json_output["changed"] = True
            self.json_output["id"] = item_id
            if auto_exit:
                self.exit_json(**self.json_output)
            return self.json_output

        detail = response["json"].get("detail", response["json"]) if isinstance(response["json"], dict) else response["json"]
        self.fail_json(msg="Unable to delete {0} {1}: {2}".format(item_type, item_name, detail))

    def create_if_needed(self, existing_item, new_item, endpoint, item_type="unknown", on_create=None, auto_exit=True):
        if existing_item:
            if auto_exit:
                self.exit_json(**self.json_output)
            return existing_item

        response = self.post_endpoint(endpoint, data=new_item)
        if response["status_code"] not in (200, 201):
            detail = response["json"].get("detail", response["json"]) if isinstance(response["json"], dict) else response["json"]
            self.fail_json(msg="Unable to create {0}: {1}".format(item_type, detail), response=response)

        self.json_output["changed"] = True
        self.json_output["id"] = response["json"]["id"]
        if "name" in response["json"]:
            self.json_output["name"] = response["json"]["name"]

        if on_create is not None:
            on_create(self, response["json"])
        elif auto_exit:
            self.exit_json(**self.json_output)
        return response["json"]

    def update_if_needed(self, existing_item, new_item, endpoint, item_type="unknown", on_update=None, auto_exit=True):
        if not existing_item:
            raise RuntimeError("update_if_needed called incorrectly without existing_item")

        item_id = existing_item["id"]
        item_name = existing_item.get("name", item_id)
        self.json_output["id"] = item_id

        if not self.objects_could_be_different(existing_item, new_item):
            if auto_exit:
                self.exit_json(**self.json_output)
            return existing_item

        response = self.patch_endpoint(self.item_path(endpoint, item_id), data=new_item)
        if response["status_code"] == 200:
            self.json_output["changed"] = True
            if on_update is not None:
                on_update(self, response["json"])
            elif auto_exit:
                self.exit_json(**self.json_output)
            return response["json"]

        detail = response["json"].get("detail", response["json"]) if isinstance(response["json"], dict) else response["json"]
        self.fail_json(msg="Unable to update {0} {1}: {2}".format(item_type, item_name, detail), response=response)

    def create_or_update_if_needed(self, existing_item, new_item, endpoint, item_type="unknown", on_create=None, on_update=None, auto_exit=True):
        for key in list(new_item.keys()):
            if key in self.argument_spec:
                param_spec = self.argument_spec[key]
                if param_spec.get("type") == "bool" and new_item[key] is None:
                    new_item.pop(key)

        if existing_item:
            return self.update_if_needed(existing_item, new_item, endpoint, item_type=item_type, on_update=on_update, auto_exit=auto_exit)
        return self.create_if_needed(existing_item, new_item, endpoint, item_type=item_type, on_create=on_create, auto_exit=auto_exit)

    ENCRYPTED_STRING = "$encrypted$"

    @staticmethod
    def has_encrypted_values(obj):
        if isinstance(obj, dict):
            for val in obj.values():
                if OrchestratorAPIModule.has_encrypted_values(val):
                    return True
        elif isinstance(obj, list):
            for val in obj:
                if OrchestratorAPIModule.has_encrypted_values(val):
                    return True
        elif obj == OrchestratorAPIModule.ENCRYPTED_STRING:
            return True
        return False

    @staticmethod
    def fields_could_be_same(old_field, new_field):
        if isinstance(old_field, dict) and isinstance(new_field, dict):
            if set(old_field.keys()) != set(new_field.keys()):
                return False
            for key in new_field.keys():
                if not OrchestratorAPIModule.fields_could_be_same(old_field[key], new_field[key]):
                    return False
            return True
        if old_field == OrchestratorAPIModule.ENCRYPTED_STRING:
            return True
        return bool(new_field == old_field)

    def objects_could_be_different(self, old, new, field_set=None, warning=False):
        if field_set is None:
            field_set = set(key for key in new.keys() if key not in ("created_at", "updated_at", "id"))
        for field in field_set:
            new_field = new.get(field, None)
            old_field = old.get(field, None)
            if old_field != new_field:
                if self.update_secrets or (not self.fields_could_be_same(old_field, new_field)):
                    return True
            elif self.has_encrypted_values(new_field) or field not in new:
                if self.update_secrets or (not self.fields_could_be_same(old_field, new_field)):
                    return True
        return False

    def wait_on_execution(self, execution_id, timeout=300, interval=2):
        start = time.time()
        current_interval = interval
        while True:
            response = self.get_endpoint(self.item_path("executions", execution_id))
            if response["status_code"] != 200:
                self.fail_json(msg="Failed to get execution status", response=response)

            execution = response["json"]
            status = execution.get("status")
            self.json_output["status"] = status
            self.json_output["execution_id"] = execution_id

            if status in _TERMINAL_EXECUTION_STATUSES:
                self.json_output["execution"] = execution
                if status in ("failed", "completed_with_errors"):
                    self.fail_json(msg="Execution {0} finished with status {1}".format(execution_id, status), **self.json_output)
                return execution

            if timeout and time.time() - start > timeout:
                self.fail_json(msg="Monitoring of execution {0} aborted due to timeout".format(execution_id), **self.json_output)

            time.sleep(current_interval)
            current_interval = min(current_interval * 1.5, 30)


class OrchestratorAPIModule(OrchestratorModule):
    def __init__(self, **kwargs):
        kwargs.setdefault("argument_spec", {})
        kwargs["argument_spec"].setdefault(
            "update_secrets",
            dict(type="bool", default=False, aliases=["update_inputs"]),
        )
        super().__init__(**kwargs)
        self.update_secrets = self.params.get("update_secrets", False)
