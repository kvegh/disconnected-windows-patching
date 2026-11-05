# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Join authenticated Windows identity with independently pinned native ownership."""

import ipaddress
import re
from urllib.parse import urlsplit
from uuid import UUID
import xml.etree.ElementTree as ET

from ansible.errors import AnsibleFilterError


def require(condition, message):
    if not condition:
        raise AnsibleFilterError(message)


def identifier(value):
    try:
        result = str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise AnsibleFilterError('A genuine Windows/native computer UUID is required.') from error
    require(result != str(UUID(int=0)), 'An empty computer UUID cannot prove ownership.')
    return result


def provenance(computer, native, instance, name, guest, primary_address, pin, trust, directory, owned_guests):
    """Emit the shared Windows resource only after normal WinRM and native proof."""
    require(isinstance(trust, dict) and set(trust) == {'scheme', 'validation', 'ca_present'}
            and trust['scheme'] == 'https' and trust['validation'] in ['ignore', 'validate']
            and isinstance(trust['ca_present'], bool)
            and (trust['validation'] != 'validate' or trust['ca_present']),
            'Use the selected HTTPS policy and retain a public CA when validation is enabled.')
    require(isinstance(name, str) and re.fullmatch(r'[a-z][a-z0-9-]*-v[0-9]{2,}', name)
            and len(name) <= 15, 'Use the selected versioned Windows computer name.')
    require(isinstance(computer, dict) and isinstance(native, dict) and isinstance(guest, dict),
            'Authenticated Windows and native ownership evidence are required.')
    require(re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,14}', computer.get('computer_name', ''))
            and computer.get('computer_name', '').lower() == name
            and computer.get('os_product_type') in [2, 3],
            'The connected Windows Server does not have the selected computer identity.')
    require(computer.get('os_build') == {'2022': '20348', '2025': '26100'}[str(guest['version'])],
            'The authenticated Windows build differs from the selected golden version.')
    require(computer.get('part_of_domain') is False
            or (computer.get('part_of_domain') is True
                and computer.get('domain', '').lower() == directory.get('dns_domain', '').lower()
                and bool(directory.get('dns_domain'))),
            'An inherited or foreign Active Directory integration prevents release.')
    require(native.get('hypervisor_machine_id') == pin.get('machine_id')
            and re.fullmatch(r'[0-9a-f]{32}', native.get('hypervisor_machine_id', '')),
            'Native proof must come from the independently pinned hypervisor.')
    expected = guest['interfaces']
    require(primary_address in [nic['address'] for nic in expected],
            'The actual WinRM address must be one of the selected permanent interfaces.')
    actual = computer.get('interfaces')
    require(isinstance(actual, list) and len(actual) == len(expected),
            'Read all active Windows NICs before releasing this guest.')
    normalized = {nic.get('mac', '').lower().replace('-', ':'): nic.get('addresses') for nic in actual}
    require(len(normalized) == len(actual)
            and set(normalized) == {nic['mac'] for nic in expected}
            and all(normalized[nic['mac']] == [nic['address']] for nic in expected),
            'Windows NIC MACs and permanent IPv4 addresses must match every selected interface.')
    require(name in owned_guests and owned_guests[name] == guest,
            'Use the complete selected instance mapping when checking inherited integrations.')
    all_interfaces = [nic for owned in owned_guests.values() for nic in owned['interfaces']]
    allowed_sources = {nic['address'] for nic in all_interfaces} | {nic['dns_name'].lower() for nic in all_interfaces}
    for source in computer.get('update_urls', []):
        endpoint = urlsplit(source)
        require(endpoint.scheme in ['http', 'https'] and endpoint.hostname in allowed_sources
                and endpoint.username is None and endpoint.password is None,
                'An inherited update-service endpoint prevents guest release.')
    disk = '/opt/vms/win-' + name + '-clone.disk.qcow2'
    require(native.get('disk') == {'path': disk, 'regular': True, 'symlink': False, 'links': 1,
                                 'standalone_qcow2': True}
            and native.get('snapshots') == [],
            'Use only the selected independent clone disk without snapshots or links.')
    native_uuid = None
    interfaces = None
    for field in ['persistent_xml', 'current_xml']:
        root = ET.fromstring(native[field])
        uuid = identifier(root.findtext('uuid'))
        require(root.findtext('name') == name
                and root.findtext('description') == 'aap-disconnected-windows-clone'
                and root.findtext('title') == instance + ':' + name,
                'The native domain does not carry the exact selected instance owner marker.')
        writable = [node.find('source').get('file') if node.find('source') is not None else None
                    for node in root.findall('./devices/disk')
                    if node.get('device') == 'disk' and node.find('readonly') is None]
        require(writable == [disk], 'The native domain has an unexpected writable disk.')
        nics = root.findall('./devices/interface')
        require(len(nics) == len(expected), 'The native domain has unexpected interfaces.')
        discovered = []
        for nic, selected in zip(nics, expected):
            require(nic.get('type') == 'network' and nic.find('source') is not None
                    and nic.find('source').get('network') == selected['network']
                    and nic.find('mac') is not None
                    and nic.find('mac').get('address', '').lower() == selected['mac'],
                    'Every native NIC must match the selected network and MAC.')
            network = native['networks'][selected['network']]
            bridges = []
            for xml in [network['persistent'], network['current']]:
                definition = ET.fromstring(xml)
                bridge = definition.find('./bridge')
                require(definition.findtext('name') == selected['network'] and bridge is not None
                        and re.fullmatch(r'[A-Za-z0-9_.-]+', bridge.get('name', '')),
                        'Read the actual bridge from both native network definitions.')
                bridges.append(bridge.get('name'))
            require(bridges[0] == bridges[1], 'Persistent and current network bridges differ.')
            address = ipaddress.ip_address(selected['address'])
            require(address.version == 4 and address.is_private,
                    'Only the selected private permanent guest addresses may be released.')
            discovered.append(dict(selected, bridge=bridges[0]))
        require(native_uuid is None or (native_uuid == uuid and interfaces == discovered),
                'Persistent and current domain identity differ.')
        native_uuid, interfaces = uuid, discovered
    require(identifier(computer.get('computer_uuid')) == native_uuid,
            'Authenticated Windows CIM UUID does not match the owned native domain UUID.')
    return {'kind': 'windows', 'vm_name': name, 'instance_name': instance, 'uuid': native_uuid,
            'disk': disk, 'hypervisor_machine_id': pin['machine_id'], 'verified': True,
            'computer_name': computer['computer_name'], 'computer_uuid': native_uuid,
            'address': primary_address, 'interfaces': interfaces,
            'winrm_certificate_validated': trust['validation'] == 'validate'}


class FilterModule:
    def filters(self):
        return {'windows_guest_verified_provenance': provenance}
