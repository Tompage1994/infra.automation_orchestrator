# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  host:
    description:
      - The URL of the Automation Orchestrator instance.
      - Can also be set with the C(AO_HOST) environment variable.
    type: str
  username:
    description:
      - The username to authenticate with.
      - Can also be set with the C(AO_USERNAME) environment variable.
    type: str
  password:
    description:
      - The password to authenticate with.
      - Can also be set with the C(AO_PASSWORD) environment variable.
    type: str
  token:
    description:
      - JWT access token for Automation Orchestrator API authentication.
      - Can also be set with the C(AO_TOKEN) environment variable.
    type: raw
  verify_ssl:
    description:
      - Whether to validate TLS certificates.
      - Can also be set with the C(AO_VALIDATE_CERTS) environment variable.
    type: bool
    default: true
  request_timeout:
    description:
      - HTTP request timeout in seconds.
      - Can also be set with the C(AO_REQUEST_TIMEOUT) environment variable.
    type: float
    default: 30
"""
