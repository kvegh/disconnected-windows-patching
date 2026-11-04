# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Validate a selected Windows instance before exposing its runtime variables."""

import ipaddress
import re

from ansible.errors import AnsibleFilterError


PROFILE_KEYS = {
    'active_directory', 'wsus_client_sources', 'wsus_internal_url',
    'wsus_transfer_bind_address', 'wsus_transfer_allowed_sources',
    'wsus_transfer_base_url', 'nexus_server_settings',
    'chocolatey_source_username', 'chocolatey_source_password',
    'chocolatey_internal_source_url', 'chocolatey_baseline_source_url',
    'chocolatey_current_source_url', 'chocolatey_transfer_username',
    'chocolatey_transfer_password', 'nexus_eula_approved_distribution',
    'windows_activation_approved', 'windows_activation_network',
    'windows_activation_username', 'windows_activation_password',
    'windows_activation_targets', 'windows_demo_vm_names',
    'windows_demo_include_ad', 'windows_runtime_hypervisor',
    'windows_runtime_guests', 'windows_runtime_winrm_ready',
    'windows_runtime_winrm_ca',
}
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9-]{0,14}$')
MAC = re.compile(r'^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$')


def require(condition, message):
    if not condition:
        raise AnsibleFilterError(message)


def selected_settings(document, instance):
    """Return only reviewed variables from exactly one encrypted instance."""
    require(isinstance(instance, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', instance),
            'An explicit safe instance name is required.')
    require(isinstance(document, dict) and set(document) == {'windows_runtime'},
            'Expected one Windows runtime document.')
    record = document['windows_runtime']
    require(isinstance(record, dict) and set(record) == {'schema', 'instance', 'settings'},
            'Unexpected Windows runtime document fields.')
    require(record['schema'] == 1 and record['instance'] == instance,
            'The encrypted runtime document belongs to a different instance or schema.')
    values = record['settings']
    require(isinstance(values, dict) and not (set(values) - PROFILE_KEYS),
            'The encrypted document contains unreviewed runtime variables.')
    required = {'windows_runtime_hypervisor', 'windows_runtime_guests',
                'windows_demo_vm_names', 'windows_demo_include_ad',
                'windows_runtime_winrm_ready', 'active_directory'}
    require(required <= set(values), 'The instance runtime identity is incomplete.')
    pin = values['windows_runtime_hypervisor']
    require(isinstance(pin, dict) and set(pin) == {
        'inventory_host', 'address', 'port', 'machine_id', 'known_hosts'},
        'An exact hypervisor connection and independent machine identity are required.')
    require(isinstance(pin['machine_id'], str) and re.fullmatch(r'[0-9a-f]{32}', pin['machine_id']),
            'An independently verified hypervisor machine identity is required.')
    ipaddress.ip_address(pin['address'])
    require(isinstance(pin['port'], int) and 1 <= pin['port'] <= 65535,
            'Invalid pinned SSH port.')
    require(isinstance(pin['known_hosts'], str) and pin['known_hosts'].strip()
            and 'ssh-' in pin['known_hosts'], 'Pinned SSH host keys are required.')
    guests = values['windows_runtime_guests']
    names = values['windows_demo_vm_names']
    require(isinstance(guests, dict) and isinstance(names, list)
            and len(names) == len(set(names)) == 5 and set(names) == set(guests)
            and values['windows_demo_include_ad'] is True,
            'Exactly five distinct instance-owned Windows guests are required.')
    macs = []
    addresses = []
    for name, guest in guests.items():
        require(isinstance(name, str) and NAME.fullmatch(name),
                'Windows computer names must contain at most fifteen safe characters.')
        require(isinstance(guest, dict) and set(guest) == {'role', 'version', 'interfaces'},
                'Each owned guest needs an exact role, version and network mapping.')
        require(guest['role'] in {'managed', 'wsus', 'ad'}
                and str(guest['version']) in {'2022', '2025'}, 'Invalid guest role or version.')
        require(isinstance(guest['interfaces'], list) and 1 <= len(guest['interfaces']) <= 2,
                'Each guest needs its explicit permanent interface mapping.')
        for nic in guest['interfaces']:
            require(isinstance(nic, dict) and set(nic) == {'network', 'mac', 'address', 'dns_name'},
                    'An exact network, NIC, address and DNS name are required.')
            require(isinstance(nic['network'], str) and re.fullmatch(r'[A-Za-z0-9_.-]+', nic['network'])
                    and isinstance(nic['mac'], str) and MAC.fullmatch(nic['mac']),
                    'Invalid permanent Windows interface mapping.')
            ipaddress.ip_address(nic['address'])
            require(isinstance(nic['dns_name'], str)
                    and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', nic['dns_name']),
                    'An exact safe reservation name is required.')
            macs.append(nic['mac'])
            addresses.append((nic['network'], nic['address']))
    require(len(macs) == len(set(macs)) and len(addresses) == len(set(addresses)),
            'Guests must not share NICs or an address on the same network.')
    ad = values['active_directory']
    require(isinstance(ad, dict) and ad.get('hostname') in guests
            and guests[ad['hostname']]['role'] == 'ad', 'The AD host must be one of the five owned guests.')
    require(ad.get('fqdn') == ad['hostname'] + '.' + ad.get('dns_domain', ''),
            'The AD certificate and DNS identity must match the selected forest.')
    require(isinstance(values['windows_runtime_winrm_ready'], bool),
            'WinRM bootstrap readiness must be explicit.')
    if values['windows_runtime_winrm_ready']:
        require(isinstance(values.get('windows_runtime_winrm_ca'), str)
                and '-----BEGIN CERTIFICATE-----' in values['windows_runtime_winrm_ca'],
                'Validated WinRM requires its selected public CA.')
    return values


class FilterModule:
    def filters(self):
        return {'windows_runtime_selected_settings': selected_settings}
