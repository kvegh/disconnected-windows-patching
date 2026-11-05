# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Manage only a selected clone's exact DHCP/DNS tuples after conflict checks."""

import ipaddress
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def virsh(*args):
    return subprocess.check_output(['virsh', *args], text=True).strip()


def inspect(record, network_xml, leases):
    """Build exact operations; reject conflicting, ambiguous or shared records."""
    root = ET.fromstring(network_xml)
    address = ipaddress.ip_address(record['address'])
    candidates = [node for node in root.findall('ip') if node.get('address') and address in
                  ipaddress.ip_network(node.get('address') + '/' +
                                       (node.get('prefix') or node.get('netmask')), strict=False)]
    if len(candidates) != 1:
        raise ValueError('The selected address does not belong to exactly one libvirt subnet.')
    dhcp = candidates[0].findall('dhcp/host')
    expected = {'mac': record['mac'], 'ip': record['address'], 'name': record['dns_name']}
    related = [node for node in dhcp if node.get('ip') == record['address']
               or node.get('mac', '').lower() == record['mac'] or node.get('name') == record['dns_name']]
    if len(related) > 1 or any(node.attrib != expected for node in related):
        raise ValueError('A selected DHCP address, MAC or name belongs to a different reservation.')
    for lease in leases:
        if lease.get('ipaddr') == record['address'] and lease.get('mac', '').lower() != record['mac']:
            raise ValueError('The selected address is leased to another NIC.')
    dns_related = [node for node in root.findall('dns/host') if node.get('ip') == record['address']
                   or record['dns_name'] in [child.text for child in node.findall('hostname')]]
    if len(dns_related) > 1 or any(node.attrib != {'ip': record['address']}
                                  or [child.text for child in node.findall('hostname')] != [record['dns_name']]
                                  for node in dns_related):
        raise ValueError('A selected DNS address or name belongs to a different or shared record.')
    dns = ET.Element('host', {'ip': record['address']})
    ET.SubElement(dns, 'hostname').text = record['dns_name']
    return {'network': record['network'],
            'dhcp_exists': bool(related), 'dns_exists': bool(dns_related),
            'dhcp_xml': ET.tostring(ET.Element('host', expected), encoding='unicode'),
            'dns_xml': ET.tostring(dns, encoding='unicode')}


def main():
    mode = sys.argv[1]
    if mode not in {'preview', 'reserve', 'remove'}:
        raise ValueError('Use preview, reserve or remove.')
    record = json.load(sys.stdin)
    targets = record['interfaces']
    if mode == 'reserve':
        disk = Path('/opt/vms/win-' + record['name'] + '-clone.disk.qcow2')
        if not disk.is_file() or disk.is_symlink():
            raise ValueError('Create the selected standalone clone before any fresh DHCP/DNS reservation.')
    for name in virsh('list', '--all', '--name').splitlines():
        root = ET.fromstring(virsh('dumpxml', name, '--inactive'))
        for nic in root.findall('./devices/interface'):
            mac = nic.find('mac')
            if mac is not None and any(mac.get('address', '').lower() == target['mac'] for target in targets):
                if name != record['name']:
                    raise ValueError('A selected NIC belongs to another domain.')
                if mode == 'remove':
                    raise ValueError('Remove the validated owned domain before removing its reservations.')
    plans = []
    for nic in targets:
        # Read both definitions before changing either: unexpected drift is fatal.
        live = virsh('net-dumpxml', nic['network'])
        saved = virsh('net-dumpxml', nic['network'], '--inactive')
        leases_xml = virsh('net-dhcp-leases', nic['network'])
        leases = []
        for line in leases_xml.splitlines()[2:]:
            fields = line.split()
            if len(fields) >= 5:
                leases.append({'mac': fields[2].lower(), 'ipaddr': fields[4].split('/')[0]})
        current = inspect(nic, live, leases)
        persistent = inspect(nic, saved, leases)
        if current != persistent:
            raise ValueError('Live and persistent ownership of a selected network resource differ.')
        plans.append(current)
    changed = False
    for plan in plans:
        for kind in ('dns', 'dhcp'):
            exists = plan[kind + '_exists']
            operation = 'add-last' if mode == 'reserve' and not exists else 'delete' if mode == 'remove' and exists else None
            if operation:
                virsh('net-update', plan['network'], operation,
                      'dns-host' if kind == 'dns' else 'ip-dhcp-host',
                      plan[kind + '_xml'], '--live', '--config')
                changed = True
    print(json.dumps({'mode': mode, 'changed': changed, 'resources': plans}))


if __name__ == '__main__':
    # Match the existing NIC/disk lifecycle boundary; no reservation may appear after cleanup wins.
    with open('/run/lock/aap-windows-management-interface.lock', 'a', encoding='utf-8') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        main()
