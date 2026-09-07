# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Connection configuration for the Automation Orchestrator API.

This module is part of the platform SDK and is not Ansible-specific beyond
its use of ``os.environ`` for the standard AO_* environment variable
fallbacks (mirrored from the legacy module_utils implementations).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import configparser
import logging
import os
from dataclasses import dataclass, field
from os.path import expanduser, isfile, join, split
from typing import Any, Dict, Optional

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)

CONFIG_FILE_NAME = ".ao_cli.cfg"

# Maps config-file keys (INI options or YAML keys) to AOConfig attribute names.
_CONFIG_FILE_KEYS = {
    "ao_host": "base_url",
    "host": "base_url",
    "ao_username": "username",
    "username": "username",
    "ao_password": "password",
    "password": "password",
    "ao_token": "token",
    "token": "token",
    "ao_client_id": "client_id",
    "client_id": "client_id",
    "ao_client_secret": "client_secret",
    "client_secret": "client_secret",
    "ao_validate_certs": "verify_ssl",
    "validate_certs": "verify_ssl",
    "ao_request_timeout": "request_timeout",
    "request_timeout": "request_timeout",
}


@dataclass
class AOConfig:
    """Automation Orchestrator connection configuration.

    Generic configuration object usable from any entry point (action
    plugin, lookup plugin, CLI).
    """

    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    verify_ssl: bool = True
    request_timeout: float = 30.0
    config_file: Optional[str] = None
    cache: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.base_url = self._normalize_url(self.base_url)

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return url
        url = url.strip()
        if not url.startswith(("https://", "http://")):
            url = f"https://{url}"
        return url.rstrip("/")


def _load_config_file(path: str) -> Dict[str, Any]:
    """Parse a single config file (INI or YAML) into raw key/value pairs."""
    values: Dict[str, Any] = {}
    if path.endswith((".yml", ".yaml")):
        if not HAS_YAML:
            logger.warning("PyYAML is required to read config file %s; skipping", path)
            return values
        with open(path, "r") as handle:
            data = yaml.safe_load(handle) or {}
        values.update(data)
        return values

    parser = configparser.ConfigParser()
    parser.read(path)
    for section in parser.sections():
        for option, value in parser.items(section):
            values[option] = value
    return values


def load_ao_config_files(explicit_path: Optional[str] = None) -> Dict[str, Any]:
    """Read AO CLI config files from the standard search path.

    Search order (later files override earlier ones), mirroring the legacy
    ``OrchestratorModule.load_config_files()`` behaviour: ``/etc``, the
    user's home directory, each directory from the current working
    directory up to the filesystem root, and finally an explicit path.
    """
    candidates = [
        "/etc/automation_orchestrator/ao_cli.cfg",
        join(expanduser("~"), CONFIG_FILE_NAME),
    ]
    local_dir = os.getcwd()
    candidates.append(join(local_dir, CONFIG_FILE_NAME))
    while split(local_dir)[1]:
        local_dir = split(local_dir)[0]
        candidates.append(join(local_dir, CONFIG_FILE_NAME))
    if explicit_path:
        candidates.append(explicit_path)

    merged: Dict[str, Any] = {}
    for candidate in candidates:
        if isfile(candidate) and os.access(candidate, os.R_OK):
            try:
                merged.update(_load_config_file(candidate))
            except Exception as exc:  # noqa: BLE001 - config files are best-effort
                logger.warning("Failed to read config file %s: %s", candidate, exc)
    return merged


def _first(*values):
    for value in values:
        if value is not None:
            return value
    return None


def extract_ao_config(
    task_args: Optional[Dict[str, Any]] = None,
    host_vars: Optional[Dict[str, Any]] = None,
    required: bool = True,
) -> AOConfig:
    """Extract :class:`AOConfig` from task arguments, host vars, env, and config files.

    Precedence (highest to lowest): task arguments, host/inventory variables,
    environment variables, AO CLI config files, built-in defaults.
    """
    task_args = task_args or {}
    host_vars = host_vars or {}

    config_file_path = _first(task_args.get("ao_config_file"), host_vars.get("ao_config_file"))
    file_values = load_ao_config_files(config_file_path)

    def resolve(param: str, env_names, file_key: Optional[str] = None):
        value = _first(task_args.get(param), host_vars.get(param))
        if value is not None:
            return value
        for env_name in env_names:
            if env_name in os.environ:
                return os.environ[env_name]
        if file_key is not None and file_key in file_values:
            return file_values[file_key]
        return None

    base_url = resolve("ao_host", ["AO_HOST"], "ao_host")
    if base_url is None:
        base_url = file_values.get("host")
    username = resolve("ao_username", ["AO_USERNAME"], "ao_username")
    password = resolve("ao_password", ["AO_PASSWORD"], "ao_password")
    token = resolve("ao_token", ["AO_TOKEN"], "ao_token")
    client_id = resolve("ao_client_id", ["AO_CLIENT_ID"], "ao_client_id")
    client_secret = resolve("ao_client_secret", ["AO_CLIENT_SECRET"], "ao_client_secret")

    # Token may be supplied as a dict (as returned by a hypothetical token
    # module); extract the raw string, same as the legacy implementation.
    if isinstance(token, dict):
        token = token.get("token") or token.get("access_token")

    # 'in' checks (not 'or' chains) so an explicit False is not dropped.
    verify_keys = ("ao_validate_certs",)
    verify_ssl = next(
        (task_args[k] for k in verify_keys if k in task_args),
        next(
            (host_vars[k] for k in verify_keys if k in host_vars),
            None,
        ),
    )
    if verify_ssl is None:
        env_value = os.environ.get("AO_VALIDATE_CERTS")
        if env_value is not None:
            verify_ssl = env_value.strip().lower() not in ("false", "0", "no")
    if verify_ssl is None and "ao_validate_certs" in file_values:
        raw = file_values["ao_validate_certs"]
        verify_ssl = raw if isinstance(raw, bool) else str(raw).strip().lower() not in ("false", "0", "no")
    if verify_ssl is None:
        verify_ssl = True

    request_timeout = resolve("ao_request_timeout", ["AO_REQUEST_TIMEOUT"], "ao_request_timeout")
    request_timeout = float(request_timeout) if request_timeout is not None else 30.0

    if required and not base_url:
        raise ValueError("ao_host must be provided as a task parameter, AO_HOST environment variable, or config file")

    return AOConfig(
        base_url=base_url or "",
        username=username,
        password=password,
        token=token,
        client_id=client_id,
        client_secret=client_secret,
        verify_ssl=verify_ssl,
        request_timeout=request_timeout,
        config_file=config_file_path,
    )
