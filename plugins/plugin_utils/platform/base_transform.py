# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Base transformation mixin for bidirectional Ansible <-> API data transformation."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from abc import ABC
from dataclasses import asdict
from typing import Any, Dict, Optional, Type, TypeVar, Union

from .types import TransformContext

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BaseTransformMixin(ABC):
    """Bidirectional transformation mixin shared by Ansible and API dataclasses.

    Subclasses declare ``_field_mapping`` (and optionally
    ``_transform_registry``) and get ``to_ansible()`` / forward transforms
    for free via the generic logic below.
    """

    _field_mapping: Optional[Dict] = None
    _transform_registry: Optional[Dict] = None

    # Set True on mixins for resources with no list/create endpoint that are
    # always addressed by a fixed path (e.g. settings).
    is_singleton: bool = False

    def to_ansible(self, context: Optional[Union[TransformContext, Dict[str, Any]]] = None) -> Any:
        ctx = self._normalize_context(context)
        return self._transform(target_class=self._get_ansible_class(), direction="reverse", context=ctx)

    @staticmethod
    def _normalize_context(context: Optional[Union[TransformContext, Dict[str, Any]]]) -> TransformContext:
        if context is None:
            raise ValueError("Context is required for transformation")
        if isinstance(context, TransformContext):
            return context
        if isinstance(context, dict):
            return TransformContext(
                client=context["client"],
                cache=context.get("cache", {}),
                api_version=context.get("api_version", "1"),
                operation=context.get("operation"),
            )
        raise TypeError(f"Context must be TransformContext or dict, got {type(context)}")

    def _transform(self, target_class: Type[T], direction: str, context: TransformContext) -> T:
        source_data = asdict(self)
        mapping = self._field_mapping or {}

        if direction == "forward":
            transformed_data = self._apply_forward_mapping(source_data, mapping, context)
        elif direction == "reverse":
            transformed_data = self._apply_reverse_mapping(source_data, mapping, context)
        else:
            raise ValueError(f"Invalid direction: {direction}")

        transformed_data = self._post_transform_hook(transformed_data, direction, context)
        return target_class(**transformed_data)

    def _apply_forward_mapping(self, source_data: dict, mapping: dict, context: TransformContext) -> dict:
        result: Dict[str, Any] = {}
        for ansible_field, spec in mapping.items():
            value = self._get_nested(source_data, ansible_field)
            if value is None:
                continue
            if isinstance(spec, dict) and "forward_transform" in spec:
                value = self._apply_transform(value, spec["forward_transform"], context)
            if isinstance(spec, str):
                target_field = spec
            elif isinstance(spec, dict):
                target_field = spec.get("api_field", ansible_field)
            else:
                target_field = ansible_field
            self._set_nested(result, target_field, value)
        return result

    def _apply_reverse_mapping(self, source_data: dict, mapping: dict, context: TransformContext) -> dict:
        result: Dict[str, Any] = {}
        for ansible_field, spec in mapping.items():
            if isinstance(spec, str):
                source_field = spec
            elif isinstance(spec, dict):
                source_field = spec.get("api_field", ansible_field)
            else:
                source_field = ansible_field
            value = self._get_nested(source_data, source_field)
            if value is None:
                continue
            if isinstance(spec, dict) and "reverse_transform" in spec:
                value = self._apply_transform(value, spec["reverse_transform"], context)
            self._set_nested(result, ansible_field, value)
        return result

    def _apply_transform(self, value: Any, transform_name: str, context: TransformContext) -> Any:
        if self._transform_registry and transform_name in self._transform_registry:
            return self._transform_registry[transform_name](value, context)
        logger.warning("Transform '%s' not found in registry, returning value unchanged", transform_name)
        return value

    def _get_nested(self, data: dict, path: str) -> Any:
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return None
            else:
                return None
        return current

    def _set_nested(self, data: dict, path: str, value: Any) -> None:
        keys = path.split(".")
        current = data
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = value

    def _post_transform_hook(self, data: dict, direction: str, context: TransformContext) -> dict:
        """Hook for module-specific post-processing after transformation. Default: no-op."""
        return data

    @classmethod
    def _get_api_class(cls) -> Type:
        raise NotImplementedError(f"{cls.__name__} must implement _get_api_class()")

    @classmethod
    def _get_ansible_class(cls) -> Type:
        raise NotImplementedError(f"{cls.__name__} must implement _get_ansible_class()")

    def validate(self) -> bool:
        """Hook for module-specific validation. Default: always valid."""
        return True
