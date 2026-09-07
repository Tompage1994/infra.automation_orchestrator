# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Dynamic class loader for version-specific resource implementations."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib
import inspect
import logging
from typing import Dict, Optional, Tuple, Type

from .base_transform import BaseTransformMixin
from .registry import APIVersionRegistry

logger = logging.getLogger(__name__)

_COLLECTION_NAMESPACE = "ansible_collections.infra.automation_orchestrator.plugins.plugin_utils"


def _to_pascal_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


class DynamicClassLoader:
    """Loads the Ansible dataclass, API dataclass, and transform mixin for a module+version."""

    def __init__(self, registry: APIVersionRegistry):
        self.registry = registry
        self._class_cache: Dict[str, Tuple[Type, Type, Type]] = {}

    def load_classes_for_module(self, module_name: str, api_version: str) -> Tuple[Type, Type, Type]:
        best_version = self.registry.find_best_version(api_version, module_name)
        if not best_version:
            raise ValueError(f"No compatible API version found for module '{module_name}' with requested version '{api_version}'")

        cache_key = f"{module_name}_{best_version.replace('.', '_')}"
        if cache_key in self._class_cache:
            return self._class_cache[cache_key]

        ansible_class = self._load_ansible_class(module_name)
        api_class, mixin_class = self._load_api_classes(module_name, best_version)

        result = (ansible_class, api_class, mixin_class)
        self._class_cache[cache_key] = result
        return result

    def _load_ansible_class(self, module_name: str) -> Type:
        module_path = f"{_COLLECTION_NAMESPACE}.ansible_models.{module_name}"
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(f"Failed to import Ansible module {module_path}: {exc}") from exc

        class_name = f"Ansible{_to_pascal_case(module_name)}"
        if hasattr(module, class_name):
            return getattr(module, class_name)

        target_lower = class_name.lower()
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.lower() == target_lower:
                return obj
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("Ansible"):
                return obj

        raise ValueError(f"No Ansible dataclass found in {module_path} (expected {class_name})")

    def _load_api_classes(self, module_name: str, api_version: str) -> Tuple[Type, Type]:
        version_normalized = api_version.replace(".", "_")
        module_path = f"{_COLLECTION_NAMESPACE}.api.v{version_normalized}.{module_name}"
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(f"Failed to import API module {module_path}: {exc}") from exc

        pascal = _to_pascal_case(module_name)
        api_class_name = f"API{pascal}_v{version_normalized}"
        api_class = self._find_class_in_module(module, [api_class_name, f"API{pascal}", "API*"], f"API dataclass for {module_name}")

        mixin_class_name = f"{pascal}TransformMixin_v{version_normalized}"
        mixin_class = self._find_class_in_module(
            module, [mixin_class_name, f"{pascal}TransformMixin", "*TransformMixin"], f"Transform mixin for {module_name}", base_class=BaseTransformMixin
        )
        return api_class, mixin_class

    def _find_class_in_module(self, module, patterns: list, description: str, base_class: Optional[Type] = None) -> Type:
        classes = inspect.getmembers(module, inspect.isclass)
        if base_class:
            classes = [(name, cls) for name, cls in classes if issubclass(cls, base_class) and cls != base_class]

        for pattern in patterns:
            if "*" in pattern:
                prefix, _sep, suffix = pattern.partition("*")
                p_lower, s_lower = prefix.lower(), suffix.lower()
                for name, cls in classes:
                    n_lower = name.lower()
                    if n_lower.startswith(p_lower) and n_lower.endswith(s_lower):
                        return cls
            else:
                pat_lower = pattern.lower()
                for name, cls in classes:
                    if name.lower() == pat_lower:
                        return cls

        raise ValueError(f"No {description} found in {module.__name__}. Tried patterns: {patterns}")
