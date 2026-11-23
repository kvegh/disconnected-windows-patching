# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Read one exact Windows clone and its native networks without changing libvirt."""

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    request = json.load(sys.stdin)
    if set(request) != {'name', 'hypervisor_machine_id'}:
        raise ValueError('Read only the exact selected name and independent hypervisor identity.')
    name = request['name']
    if not re.fullmatch(r'[a-z][a-z0-9-]*-v[0-9]{2,}', name) or len(name) > 15:
        raise ValueError('A versioned Windows name of at most fifteen characters is required.')
    machine_id = Path('/etc/machine-id').read_text().strip()
    if machine_id != request['hypervisor_machine_id']:
        raise ValueError('Unexpected hypervisor machine identity.')

    def virsh(*args):
        return subprocess.check_output(['virsh', '--readonly', '--connect', 'qemu:///system', *args], text=True).strip()

    persistent = virsh('dumpxml', name, '--inactive')
    current = virsh('dumpxml', name)
    root = ET.fromstring(persistent)
    networks = {node.get('network') for node in root.findall('./devices/interface/source')}
    if not networks or None in networks:
        raise ValueError('Only explicit libvirt network interfaces are supported.')
    definitions = {network: {'persistent': virsh('net-dumpxml', network, '--inactive'),
                             'current': virsh('net-dumpxml', network)} for network in networks}
    path = '/opt/vms/win-' + name + '-clone.disk.qcow2'
    metadata = os.stat(path, follow_symlinks=False)
    image = json.loads(subprocess.check_output(['qemu-img', 'info', '--force-share', '--output=json', path], text=True))
    shared = []
    for domain in virsh('list', '--all', '--name').splitlines():
        if domain != name and any(node.get('file') == path for node in
                                  ET.fromstring(virsh('dumpxml', domain, '--inactive')).findall('./devices/disk/source')):
            shared.append(domain)
    if shared:
        raise ValueError('Another native domain references this clone disk.')
    print(json.dumps({'hypervisor_machine_id': machine_id, 'persistent_xml': persistent, 'current_xml': current,
                      'networks': definitions, 'snapshots': virsh('snapshot-list', name, '--name').splitlines(),
                      'disk': {'path': path, 'regular': stat.S_ISREG(metadata.st_mode),
                               'symlink': stat.S_ISLNK(metadata.st_mode), 'links': metadata.st_nlink,
                               'standalone_qcow2': image.get('format') == 'qcow2' and 'backing-filename' not in image}}))


if __name__ == '__main__':
    main()
