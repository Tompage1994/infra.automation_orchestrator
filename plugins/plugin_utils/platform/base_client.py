# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Base API client — abstract interface for Automation Orchestrator API communication."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .config import AOConfig
from .loader import DynamicClassLoader
from .registry import APIVersionRegistry

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """Abstract base class for Automation Orchestrator API clients.

    Unlike ``ansible.platform``, AO is a single service with a single API
    version, so there is no persistent-manager/direct-mode split here — but
    the shared layers (version-aware class loading, error taxonomy, CRUD via
    transform mixins, lookup caching) are kept in the same shape so this SDK
    can be aligned with ``ansible.platform`` later.
    """

    def __init__(self, config: AOConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.verify_ssl = config.verify_ssl
        self.request_timeout = config.request_timeout

        self.registry = APIVersionRegistry()
        self.loader = DynamicClassLoader(self.registry)

        self.api_version: Optional[str] = None
        self.cache: Dict[str, Any] = {}

        logger.info("BaseAPIClient initialized: base_url=%s", self.base_url)

    @abstractmethod
    def _detect_api_version(self) -> str:
        """Return the API version to use. AO currently only ships v1."""

    @abstractmethod
    def _authenticate(self) -> None:
        """Authenticate with Automation Orchestrator.

        Raises:
            AuthenticationError: If authentication fails.
        """

    @abstractmethod
    def execute(self, operation: str, module_name: str, ansible_data_dict: dict) -> dict:
        """Execute a generic CRUD operation on a resource.

        Args:
            operation: One of 'create', 'update', 'delete', 'find'.
            module_name: Resource/module name (e.g. 'project', 'workflow').
            ansible_data_dict: The Ansible dataclass (or dict) describing the resource.

        Returns:
            Result as a dict in Ansible format.
        """
