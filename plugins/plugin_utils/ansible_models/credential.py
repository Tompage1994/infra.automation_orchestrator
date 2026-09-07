# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Stable Ansible-facing dataclass for the credential resource."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleCredential:
    name: str
    id: Optional[str] = None
    credential_type: Optional[str] = None
    project: Optional[str] = None
    description: Optional[str] = None
    inputs: Optional[dict] = None
    enabled: Optional[bool] = None
    labels: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
