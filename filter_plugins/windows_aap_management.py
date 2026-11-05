# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Validate the optional Windows-owned connection on the existing AAP VM."""

import ipaddress
import re
from uuid import UUID
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from ansible.errors import AnsibleFilterError


def require(condition, message):
    if not condition:
        raise AnsibleFilterError(message)


def identifier(value):
    try:
        normalized = str(UUID(value))
        require(normalized == value and UUID(value).int != 0, 'Use a canonical nonempty UUID.')
        return normalized
    except (ValueError, TypeError, AttributeError) as error:
        raise AnsibleFilterError('Use a canonical nonempty UUID.') from error


def profile(value, instance, pin, guests):
    require(isinstance(value, dict) and set(value) == {'route', 'primary', 'interface', 'prefix_length'},
            'Use one exact optional AAP connection profile.')
    route, primary, extra = value['route'], value['primary'], value['interface']
    require(isinstance(route, dict) and set(route) == {
        'vm_name', 'vm_ip', 'aap_hostname', 'hypervisor', 'guest_host_keys'}
        and route['vm_name'] == instance and route['hypervisor'] == pin
        and isinstance(route['guest_host_keys'], list) and route['guest_host_keys'],
        'The selected AAP connection must preserve its registered route and pinned hypervisor.')
    require(isinstance(primary, dict) and set(primary) == {
        'uuid', 'disk', 'address', 'mac', 'network', 'bridge', 'verified', 'hypervisor_machine_id'}
        and primary['verified'] is True and primary['hypervisor_machine_id'] == pin['machine_id']
        and primary['address'] == route['vm_ip']
        and primary['disk'] == '/opt/vms/' + instance + '.disk.qcow2',
        'Preserve all eight independently verified primary AAP ownership fields.')
    identifier(primary['uuid'])
    require(isinstance(extra, dict) and set(extra) == {
        'owner_project_id', 'network', 'bridge', 'address', 'mac', 'connection_uuid',
        'connection_name', 'attachment_created', 'connection_created'}
        and extra['owner_project_id'] == 'disconnected-windows-patching'
        and extra['attachment_created'] is True and extra['connection_created'] is True,
        'Only the exact newly owned Windows NIC and OS connection can be managed.')
    identifier(extra['connection_uuid'])
    require(isinstance(extra['connection_name'], str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', extra['connection_name']),
            'Use an exact safe persistent connection name.')
    for nic in (primary, extra):
        address = ipaddress.ip_address(nic['address'])
        private_ranges = [ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
        require(address.version == 4 and any(address in network for network in private_ranges)
                and str(address) == nic['address']
                and re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', nic['mac'])
                and not int(nic['mac'][:2], 16) & 1
                and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}', nic['network'])
                and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,14}', nic['bridge']),
                'Use exact private IPv4, unicast MAC, network and bridge identities.')
    require(all(primary[key] != extra[key] for key in ('address', 'mac', 'network', 'bridge'))
            and extra['bridge'] in pin['isolation_bridges']
            and type(value['prefix_length']) is int and 1 <= value['prefix_length'] <= 30,
            'The second NIC must remain distinct and on the enforced isolated bridge.')
    selected_subnet = ipaddress.ip_network(extra['address'] + '/' + str(value['prefix_length']), strict=False)
    for guest in guests.values():
        for nic in guest['interfaces']:
            require(nic['mac'] != extra['mac'] and nic['address'] != extra['address'],
                    'The AAP management identity conflicts with an owned Windows guest.')
            if nic['network'] == extra['network']:
                require(ipaddress.ip_address(nic['address']) in selected_subnet,
                        'The AAP management connection must reach the selected isolated guests directly.')
    return value


def preserved_definition(actual, baseline, management):
    """Compare original core XML allowing only the exact owned NIC addition/removal."""
    extra = management['interface']
    before, after = ET.fromstring(baseline), ET.fromstring(actual)
    require(before.findtext('name') == management['route']['vm_name']
            and before.findtext('uuid', '').lower() == management['primary']['uuid'],
            'The captured AAP definition belongs to a different VM.')
    require(after.findtext('name') == before.findtext('name')
            and after.findtext('uuid') == before.findtext('uuid'), 'The preserved AAP identity changed.')
    for definition in (before, after):
        owned = [node for node in definition.findall('./devices/interface') if node.find('mac') is not None
                 and node.find('mac').get('address', '').lower() == extra['mac']]
        require(len(owned) <= 1, 'The declared supplemental NIC is duplicated.')
        if owned:
            node = owned[0]
            require(node.get('type') == 'network' and node.find('source') is not None
                    and node.find('source').get('network') == extra['network']
                    and node.find('alias') is not None
                    and node.find('alias').get('name') == 'ua-windows-' + extra['connection_uuid']
                    and node.find('model') is not None and node.find('model').get('type') == 'virtio',
                    'An extra interface differs from the exact Windows-owned declaration.')
            definition.find('devices').remove(node)

    def canonical(node):
        return (node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
                [canonical(child) for child in node])

    require(canonical(before) == canonical(after),
            'A preserved AAP property changed beyond its exact owned supplemental NIC removal.')
    return True


def ssh_trust(material, route):
    """Require the existing credential to pin this route's exact observed SSH keys."""
    require(isinstance(material, str) and material.strip(), 'Use the existing injected SSH host keys.')
    aliases = {route['vm_ip'], '[' + route['vm_ip'] + ']:22', urlsplit(route['aap_hostname']).hostname}
    keys = set(route['guest_host_keys'])
    observed = set()
    for line in material.splitlines():
        parts = line.split()
        if not parts or line.lstrip().startswith('#'):
            continue
        require(len(parts) >= 3 and not parts[0].startswith('@'), 'Unexpected SSH trust record shape.')
        if set(parts[0].split(',')) & aliases:
            key = ' '.join(parts[1:3])
            require(key in keys, 'The credential contains an unregistered selected-guest SSH key.')
            if {route['vm_ip'], '[' + route['vm_ip'] + ']:22'} & set(parts[0].split(',')):
                observed.add(key)
    require(bool(observed),
            'The OS SSH credential does not pin a registered selected AAP guest key at its private address '
            f'({len(observed)} of {len(keys)} registered keys; {len(material.splitlines())} input lines).')
    return True


class FilterModule:
    def filters(self):
        return {'windows_aap_management_profile': profile,
                'windows_aap_preserved_definition': preserved_definition,
                'windows_aap_management_ssh_trust': ssh_trust}
