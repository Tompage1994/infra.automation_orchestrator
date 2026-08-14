# Ansible Collection - infra.automation_orchestrator

Ansible modules and plugins for managing [Red Hat Ansible Automation Orchestrator](https://github.com/ansible-automation-platform/automation-orchestrator).

## Requirements

- Ansible 2.15 or later
- Python 3.9 or later
- Network access to an Automation Orchestrator instance

## Installation

The collection source lives at `infra.automation_orchestrator/` in this repository.

```bash
cd infra.automation_orchestrator
ansible-galaxy collection build -f && ansible-galaxy collection install -f
```

## Authentication

Modules accept connection parameters directly or via environment variables:

| Parameter | Environment variable |
|-----------|---------------------|
| `orchestrator_host` | `AO_HOST` |
| `orchestrator_username` | `AO_USERNAME` |
| `orchestrator_password` | `AO_PASSWORD` |
| `orchestrator_token` | `AO_TOKEN` |
| `validate_certs` | `AO_VALIDATE_CERTS` |

You can also store settings in `~/.ao_cli.cfg` or `/etc/automation_orchestrator/ao_cli.cfg`.

## Modules

| Module | Description |
|--------|-------------|
| `infra.automation_orchestrator.project` | Manage projects |
| `infra.automation_orchestrator.workflow` | Manage workflow definitions |
| `infra.automation_orchestrator.credential` | Manage credentials |
| `infra.automation_orchestrator.integration` | Manage integrations |
| `infra.automation_orchestrator.execution_launch` | Launch workflow executions |

## Lookup Plugins

| Plugin | Description |
|--------|-------------|
| `infra.automation_orchestrator.orchestrator_api` | Query the Automation Orchestrator REST API |

## Example Playbook

```yaml
- name: Manage Automation Orchestrator resources
  hosts: localhost
  gather_facts: false
  vars:
    ao_host: https://orchestrator.example.com
    ao_validate_certs: false
  tasks:
    - name: Ensure project exists
      infra.automation_orchestrator.project:
        orchestrator_host: "{{ ao_host }}"
        orchestrator_username: admin
        orchestrator_password: "{{ ao_password }}"
        validate_certs: "{{ ao_validate_certs }}"
        name: demo-project
        description: Demo project
        state: present
```

## Documentation

See the [Automation Orchestrator REST API documentation](https://github.com/ansible-automation-platform/automation-orchestrator/tree/main/nexus-docs/rest-api).

## License

GPL-2.0-or-later
