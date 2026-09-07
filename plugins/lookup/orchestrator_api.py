# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
name: orchestrator_api
short_description: Query the Automation Orchestrator API
description:
  - Make a GET request to the Automation Orchestrator API and return the response.
author:
  - Tom Page (@Tompage1994)
extends_documentation_fragment:
  - infra.automation_orchestrator.auth_plugin
options:
  query_params:
    description:
      - Query parameters to pass to the API endpoint.
    type: dict
    default: {}
  expect_one:
    description:
      - Fail if the API returns more than one item.
    type: bool
    default: false
  return_all:
    description:
      - Follow pagination and return all resources.
    type: bool
    default: false
  return_objects:
    description:
      - Return full resource objects instead of IDs.
    type: bool
    default: true
  return_ids:
    description:
      - Return only resource IDs.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: List workflows
  ansible.builtin.debug:
    msg: >-
      {{ lookup('infra.automation_orchestrator.orchestrator_api', 'workflows',
      host='https://orchestrator.example.com', username='admin', password='secret', verify_ssl=false) }}

- name: Get a project by name
  ansible.builtin.debug:
    msg: "{{ lookup('infra.automation_orchestrator.orchestrator_api', 'projects', query_params={'name[eq]': 'my-project'}, expect_one=true) }}"
"""

RETURN = r"""
_raw:
  description:
    - List of resources or IDs returned from the API.
"""

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

from ansible_collections.infra.automation_orchestrator.plugins.module_utils.orchestrator_api import OrchestratorAPIModule

display = Display()


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)

        module_params = {}
        for short_param, long_param in OrchestratorAPIModule.short_params.items():
            value = self.get_option(short_param)
            if value is not None:
                module_params[long_param] = value

        query_params = self.get_option("query_params") or {}
        expect_one = self.get_option("expect_one")
        return_all = self.get_option("return_all")
        return_objects = self.get_option("return_objects")
        return_ids = self.get_option("return_ids")

        module = OrchestratorAPIModule(
            argument_spec={},
            direct_params=module_params,
            error_callback=lambda message, **kwargs: display.error(message),
            warn_callback=lambda message, **kwargs: display.warning(message),
        )

        results = []
        for term in terms:
            if return_all:
                response = module.get_all_endpoint(term, **query_params)
                resources = response["json"]["resources"]
            else:
                response = module.get_endpoint(term, data=query_params)
                if response["status_code"] != 200:
                    raise AnsibleError("API request failed: {0}".format(response))
                resources = response["json"].get("resources", [response["json"]])

            if expect_one and len(resources) != 1:
                raise AnsibleError("Expected one result from {0}, got {1}".format(term, len(resources)))

            if return_ids:
                results.extend([item["id"] for item in resources])
            elif return_objects:
                results.extend(resources)
            else:
                results.extend(resources)

        return results
