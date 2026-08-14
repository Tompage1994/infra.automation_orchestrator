# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  orchestrator_host:
    description:
      - The URL of the Automation Orchestrator instance.
      - Can also be set with the C(AO_HOST) environment variable.
    type: str
    aliases: [ao_host]
  orchestrator_username:
    description:
      - The username to authenticate with.
      - Can also be set with the C(AO_USERNAME) environment variable.
    type: str
    aliases: [ao_username]
  orchestrator_password:
    description:
      - The password to authenticate with.
      - Can also be set with the C(AO_PASSWORD) environment variable.
    type: str
    aliases: [ao_password]
  orchestrator_token:
    description:
      - JWT access token for Automation Orchestrator API authentication.
      - Can also be set with the C(AO_TOKEN) environment variable.
    type: raw
    aliases: [ao_token, access_token]
  validate_certs:
    description:
      - Whether to validate TLS certificates.
      - Can also be set with the C(AO_VALIDATE_CERTS) environment variable.
    type: bool
    default: true
    aliases: [ao_validate_certs]
  request_timeout:
    description:
      - HTTP request timeout in seconds.
      - Can also be set with the C(AO_REQUEST_TIMEOUT) environment variable.
    type: float
    default: 30
    aliases: [ao_request_timeout]
  orchestrator_config_file:
    description:
      - Path to a configuration file with connection settings.
    type: path
    aliases: [ao_config_file]
"""
