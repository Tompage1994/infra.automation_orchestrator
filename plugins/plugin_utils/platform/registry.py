# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""API version registry for dynamic version discovery.

AO currently only ships API v1, but this registry scans the filesystem the
same way ``ansible.platform``'s does, so adding ``api/v2/`` later needs no
changes here.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from packaging import version

    def _version_key(value: str):
        return version.parse(value)

except ImportError:
    import re

    def _version_key(value: str):
        parts = re.findall(r"\d+", value)
        return [int(p) for p in parts] if parts else [0]


class APIVersionRegistry:
    """Discovers available API versions and the modules implemented for each."""

    def __init__(self, api_base_path: Optional[str] = None, ansible_models_path: Optional[str] = None):
        if api_base_path is None:
            current_file = Path(__file__)
            plugin_utils = current_file.parent.parent
            api_base_path = str(plugin_utils / "api")
        if ansible_models_path is None:
            current_file = Path(__file__)
            plugin_utils = current_file.parent.parent
            ansible_models_path = str(plugin_utils / "ansible_models")

        self.api_base_path = Path(api_base_path)
        self.ansible_models_path = Path(ansible_models_path)

        self.versions: Dict[str, List[str]] = {}
        self.module_versions: Dict[str, List[str]] = {}

        self._discover_versions()

    def _discover_versions(self) -> None:
        if not self.api_base_path.exists():
            logger.warning("API base path not found: %s", self.api_base_path)
            return

        for version_dir in self.api_base_path.iterdir():
            if not version_dir.is_dir() or not version_dir.name.startswith("v"):
                continue

            version_str = version_dir.name[1:].replace("_", ".")
            module_files = [f for f in version_dir.glob("*.py") if not f.name.startswith("_")]
            module_names = [f.stem for f in module_files]

            self.versions[version_str] = module_names
            for module_name in module_names:
                self.module_versions.setdefault(module_name, []).append(version_str)

        for module_name in self.module_versions:
            self.module_versions[module_name].sort(key=_version_key)

        logger.info("Discovered %s API version(s): %s", len(self.versions), sorted(self.versions.keys(), key=_version_key))

    def get_supported_versions(self) -> List[str]:
        return sorted(self.versions.keys(), key=_version_key)

    def get_latest_version(self) -> Optional[str]:
        versions = self.get_supported_versions()
        return versions[-1] if versions else None

    def get_modules_for_version(self, api_version: str) -> List[str]:
        return self.versions.get(api_version, [])

    def get_versions_for_module(self, module_name: str) -> List[str]:
        return self.module_versions.get(module_name, [])

    def find_best_version(self, requested_version: str, module_name: str) -> Optional[str]:
        """Find the best available version for a module: exact, closest lower, then closest higher."""
        available = self.get_versions_for_module(module_name)
        if not available:
            logger.error("Module '%s' not found in any API version", module_name)
            return None

        if requested_version in available:
            return requested_version

        requested_key = _version_key(requested_version)
        available_keyed = [(v, _version_key(v)) for v in available]

        lower_versions = [(v, k) for v, k in available_keyed if k <= requested_key]
        if lower_versions:
            best = max(lower_versions, key=lambda x: x[1])[0]
            logger.warning("Using version %s for %s (requested %s, closest lower version)", best, module_name, requested_version)
            return best

        higher_versions = [(v, k) for v, k in available_keyed if k > requested_key]
        if higher_versions:
            best = min(higher_versions, key=lambda x: x[1])[0]
            logger.warning("Using version %s for %s (requested %s, closest higher version)", best, module_name, requested_version)
            return best

        return None

    def module_supports_version(self, module_name: str, api_version: str) -> bool:
        return api_version in self.get_versions_for_module(module_name)
