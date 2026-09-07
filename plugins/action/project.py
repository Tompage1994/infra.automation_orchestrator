#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.infra.automation_orchestrator.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.ansible_models.project import AnsibleProject


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "project"
    MODEL_CLASS = AnsibleProject
