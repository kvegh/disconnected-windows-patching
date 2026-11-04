# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Inspect exact instance-owned Windows clones without changing libvirt."""

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET


def inspect(instance, guests, domains):
    result = {}
    for name, expected in guests.items():
        if name not in domains:
            raise ValueError('A selected Windows guest is absent; a complete fresh preview is required.')
        root = ET.fromstring(domains[name])
        disk = '/opt/vms/win-' + name + '-clone.disk.qcow2'
        writable = [node.find('source').get('file') if node.find('source') is not None else None
                    for node in root.findall('./devices/disk')
                    if node.get('device') == 'disk' and node.find('readonly') is None]
        nics = [{'mac': node.find('mac').get('address', '').lower(),
                 'network': node.find('source').get('network')}
                for node in root.findall('./devices/interface')
                if node.find('mac') is not None and node.find('source') is not None]
        selected_nics = [{'mac': nic['mac'], 'network': nic['network']} for nic in expected['interfaces']]
        uuid = root.findtext('uuid')
        if (root.findtext('name') != name or root.findtext('description') != 'aap-disconnected-windows-clone'
                or root.findtext('title') != instance + ':' + name
                or writable != [disk] or nics != selected_nics
                or not isinstance(uuid, str)
                or re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', uuid) is None
                or uuid == '00000000-0000-0000-0000-000000000000'):
            raise ValueError('An unexpected guest identity, owner marker, disk or NIC prevents decommission.')
        for other, xml in domains.items():
            if other != name and any(node.get('file') == disk
                                     for node in ET.fromstring(xml).findall('./devices/disk/source')):
                raise ValueError('A selected clone disk is referenced by another domain.')
        result[name] = {'uuid': uuid, 'disk': disk, 'interfaces': expected['interfaces']}
    return result


def main():
    record = json.load(sys.stdin)
    def virsh(*args):
        return subprocess.check_output(['virsh', '--readonly', '--connect', 'qemu:///system', *args], text=True).strip()
    domains = {name: virsh('dumpxml', name, '--inactive')
               for name in virsh('list', '--all', '--name').splitlines()}
    owned = inspect(record['instance'], record['guests'], domains)
    for name, guest in owned.items():
        metadata = os.stat(guest['disk'], follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or Path(guest['disk']).is_symlink():
            raise ValueError('Expected a regular, non-symlinked owned clone disk.')
        if virsh('snapshot-list', name, '--name'):
            raise ValueError('A selected guest has snapshots; explicit review is required.')
    print(json.dumps({'instance': record['instance'], 'domains': owned, 'read_only': True}))


if __name__ == '__main__':
    main()
