# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  state:
    description:
      - Desired state of the resource.
      - V(present) creates the resource if it does not exist, and updates it if it does.
      - V(absent) deletes the resource if it exists.
      - V(exists) only checks whether the resource exists, without making any changes.
    type: str
    choices: [present, absent, exists]
    default: present
"""
