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
    'windows_runtime_recovery_pin',
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
    if 'windows_runtime_recovery_pin' in values:
        recovery = values['windows_runtime_recovery_pin']
        require(isinstance(recovery, dict) and set(recovery) <= {
            'address', 'public_ip', 'user', 'port', 'machine_id', 'host_keys',
            'isolation_bridges', 'isolation_dns_bridges', 'machine_credential_name'}
            and {'address', 'public_ip', 'user', 'port', 'machine_id', 'host_keys',
                 'isolation_bridges', 'isolation_dns_bridges'} <= set(recovery),
            'Use the existing complete public recovery pin without passwords or private keys.')
        require(all(recovery[key] == pin[key] for key in ['address', 'port', 'machine_id'])
                and isinstance(recovery['host_keys'], list) and recovery['host_keys']
                and isinstance(recovery['user'], str) and recovery['user'] != 'root'
                and re.fullmatch(r'[a-z_][a-z0-9_-]*[$]?', recovery['user'])
                and isinstance(recovery['isolation_bridges'], list) and recovery['isolation_bridges']
                and isinstance(recovery['isolation_dns_bridges'], list)
                and set(recovery['isolation_dns_bridges']) <= set(recovery['isolation_bridges']),
                'The release connection must retain the selected independent hypervisor identity.')
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


def ldap_cleanup(authenticators, maps, directory):
    """Select only the exact test LDAP authenticator and its reviewed maps."""
    require(isinstance(authenticators, list) and isinstance(maps, list)
            and isinstance(directory, dict), 'Read complete authenticator and map ownership first.')
    require(all(isinstance(row, dict) and isinstance(row.get('id'), int)
                and isinstance(row.get('name'), str) and isinstance(row.get('configuration'), dict)
                for row in authenticators)
            and all(isinstance(row, dict) and isinstance(row.get('id'), int)
                    and isinstance(row.get('name'), str) and isinstance(row.get('authenticator'), int)
                    for row in maps), 'Unexpected authentication API shapes require review before removal.')
    prefix, fqdn = directory.get('prefix', ''), directory.get('fqdn', '')
    require(isinstance(prefix, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,19}', prefix)
            and isinstance(fqdn, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', fqdn),
            'Use the selected private test directory identity.')
    name = prefix + ' Active Directory'
    endpoint = 'ldaps://' + fqdn + ':636'
    related = [row for row in authenticators if row.get('name') == name
               or endpoint in row.get('configuration', {}).get('SERVER_URI', [])]
    require(len(related) <= 1, 'Ambiguous or shared LDAP authentication requires review.')
    own = related[0] if related else None
    if own is not None:
        require(own.get('name') == name
                and own.get('type') == 'ansible_base.authentication.authenticator_plugins.ldap'
                and own.get('configuration', {}).get('SERVER_URI') == [endpoint]
                and isinstance(own.get('id'), int), 'The selected LDAP name or endpoint belongs to another authenticator.')
    own_maps = [row for row in maps if own is not None and row.get('authenticator') == own['id']]
    allowed_names = {'Regional demo login', 'Regional demo organization'} | {
        group['region'] + ' ' + group['role'] + ' membership'
        for group in directory.get('groups', []) if group.get('scope') == 'DomainLocal'}
    require(len({row['name'] for row in own_maps}) == len(own_maps)
            and all(row.get('name') in allowed_names and isinstance(row.get('id'), int) for row in own_maps),
            'Unrecognized or duplicate LDAP maps require explicit ownership review.')
    return {'authenticator': own, 'map_names': [row['name'] for row in own_maps],
            'preserved_authenticator_ids': sorted(row['id'] for row in authenticators if row != own),
            'preserved_map_ids': sorted(row['id'] for row in maps if row not in own_maps)}


class FilterModule:
    def filters(self):
        return {'windows_runtime_selected_settings': selected_settings,
                'windows_runtime_ldap_cleanup': ldap_cleanup}
