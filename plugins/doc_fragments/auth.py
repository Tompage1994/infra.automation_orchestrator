# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  ao_host:
    description:
      - The URL of the Automation Orchestrator instance.
      - If not set, the value of the C(AO_HOST) environment variable is used.
    type: str
  ao_username:
    description:
      - The username to authenticate with.
      - If not set, the value of the C(AO_USERNAME) environment variable is used.
    type: str
  ao_password:
    description:
      - The password to authenticate with.
      - If not set, the value of the C(AO_PASSWORD) environment variable is used.
    type: str
  ao_token:
    description:
      - A pre-existing access token for Automation Orchestrator API authentication.
      - If not set, the value of the C(AO_TOKEN) environment variable is used.
    type: str
  ao_client_id:
    description:
      - OAuth 2.0 client ID for client_credentials authentication.
      - If not set, the value of the C(AO_CLIENT_ID) environment variable is used.
    type: str
  ao_client_secret:
    description:
      - OAuth 2.0 client secret for client_credentials authentication.
      - If not set, the value of the C(AO_CLIENT_SECRET) environment variable is used.
    type: str
  ao_validate_certs:
    description:
      - Whether to validate TLS certificates.
      - If not set, the value of the C(AO_VALIDATE_CERTS) environment variable is used.
    type: bool
    default: true
  ao_request_timeout:
    description:
      - HTTP request timeout in seconds.
      - If not set, the value of the C(AO_REQUEST_TIMEOUT) environment variable is used.
    type: float
    default: 30
  ao_config_file:
    description:
      - Path to an additional C(.ao_cli.cfg) configuration file with connection settings.
      - Standard locations (C(/etc/automation_orchestrator/ao_cli.cfg), C(~/.ao_cli.cfg), and
        C(.ao_cli.cfg) in the current directory or any parent) are always searched.
    type: str
notes:
  - Exactly one authentication method must be usable, either C(ao_token), C(ao_username) +
    C(ao_password), or C(ao_client_id) + C(ao_client_secret).
"""
