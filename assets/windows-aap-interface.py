# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Bound one Windows-owned AAP NIC to exact live and persistent libvirt state."""

import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET


def require(value, message):
    if not value:
        raise ValueError(message)


def run(*args, content=None):
    return subprocess.check_output(list(args), input=content, text=True).strip()


def interface(record):
    node = ET.Element('interface', {'type': 'network'})
    ET.SubElement(node, 'mac', {'address': record['mac']})
    ET.SubElement(node, 'source', {'network': record['network']})
    ET.SubElement(node, 'model', {'type': 'virtio'})
    ET.SubElement(node, 'alias', {'name': 'ua-windows-' + record['connection_uuid']})
    return ET.tostring(node, encoding='unicode')


def inspect_domain(xml, guest):
    root = ET.fromstring(xml)
    primary, extra = guest['primary'], guest['supplemental_interface']
    require(root.findtext('name') == guest['route']['vm_name']
            and root.findtext('uuid', '').lower() == primary['uuid'],
            'The selected AAP domain identity changed.')
    disks = root.findall("./devices/disk[@device='disk']")
    require(len(disks) == 1 and disks[0].get('type') == 'file'
            and disks[0].find('source').get('file') == primary['disk'],
            'The selected AAP disk identity changed.')
    nics = root.findall('./devices/interface')
    expected = {(primary['mac'], primary['network']), (extra['mac'], extra['network'])}
    observed = []
    selected = []
    for nic in nics:
        mac, source = nic.find('mac'), nic.find('source')
        require(nic.get('type') == 'network' and mac is not None and source is not None,
                'An unreviewed AAP interface is present.')
        identity = (mac.get('address', '').lower(), source.get('network'))
        require(identity in expected and identity not in observed,
                'A foreign or duplicate AAP interface is present.')
        observed.append(identity)
        if identity[0] == extra['mac']:
            require(nic.find('alias') is not None
                    and nic.find('alias').get('name') == 'ua-windows-' + extra['connection_uuid']
                    and nic.find('model') is not None and nic.find('model').get('type') == 'virtio',
                    'An existing interface lacks the exact Windows ownership marker.')
            selected.append(nic)
    require((primary['mac'], primary['network']) in observed and len(selected) <= 1,
            'The primary AAP NIC must remain unchanged.')
    return bool(selected)


def inspect_network(xml, extra, host_addresses, leases, neighbours, allow_owned=False):
    root = ET.fromstring(xml)
    require(root.findtext('name') == extra['network'] and root.find('forward') is None
            and root.find('bridge') is not None and root.find('bridge').get('name') == extra['bridge'],
            'Use only the already isolated, exact selected network and bridge.')
    wanted = ipaddress.ip_interface(extra['address'])
    require(wanted.version == 4 and wanted.ip not in (wanted.network.network_address, wanted.network.broadcast_address),
            'The supplemental address must be a usable static IPv4 host address.')
    subnets = [node for node in root.findall('ip') if node.get('address')
               and ipaddress.ip_address(node.get('address')).version == 4
               and ipaddress.ip_network(node.get('address') + '/' +
                                        (node.get('prefix') or node.get('netmask')), strict=False) == wanted.network]
    require(len(subnets) == 1 and str(wanted.ip) != subnets[0].get('address'),
            'The selected address must belong to the existing isolated subnet.')
    for item in subnets[0].findall('dhcp/range'):
        require(not (ipaddress.ip_address(item.get('start')) <= wanted.ip <= ipaddress.ip_address(item.get('end'))),
                'A static management address must be outside the dynamic DHCP pool.')
    for item in root.findall('.//dhcp/host'):
        require(item.get('ip') != str(wanted.ip) and item.get('mac', '').lower() != extra['mac'],
                'The selected static address or NIC belongs to an existing reservation.')
    require(all(node.get('ip') != str(wanted.ip) for node in root.findall('./dns/host')),
            'An existing DNS record owns the selected address.')
    require(not any(str(wanted.ip) == item.get('local') for host in host_addresses
                    for item in host.get('addr_info', [])), 'The hypervisor already owns the selected address.')
    for line in leases.splitlines()[2:]:
        fields = line.split()
        require(len(fields) < 5 or (fields[4].split('/')[0] != str(wanted.ip)
                                   and fields[2].lower() != extra['mac']),
                'A DHCP lease conflicts with the selected static identity.')
    require(all(row.get('dst') != str(wanted.ip)
                or (allow_owned and row.get('lladdr', '').lower() == extra['mac']) for row in neighbours),
            'A neighbour with another MAC owns the selected address.')


def main(request):
    guest = request['guest']
    extra, primary = dict(guest['supplemental_interface']), guest['primary']
    extra['address'] += '/' + str(request['prefix_length'])
    require(Path('/etc/machine-id').read_text().strip() == primary['hypervisor_machine_id'],
            'The connected hypervisor identity differs from the selected pin.')
    require(request['mode'] in {'ensure', 'remove', 'inspect', 'rollback', 'clone'}, 'Unsupported NIC operation.')
    require(isinstance(request['published'], bool), 'Canonical ownership must be read before native operations.')
    require(run('virsh', 'domstate', guest['route']['vm_name']) == 'running',
            'The selected AAP guest must already be running; this task never starts it.')
    live = run('virsh', 'dumpxml', guest['route']['vm_name'])
    saved = run('virsh', 'dumpxml', guest['route']['vm_name'], '--inactive')
    has_live, has_saved = inspect_domain(live, guest), inspect_domain(saved, guest)
    for state in ([], ['--inactive']):
        network = run('virsh', 'net-dumpxml', extra['network'], *state)
        inspect_network(network, extra, json.loads(run('ip', '-j', '-4', 'address', 'show')),
                        run('virsh', 'net-dhcp-leases', extra['network']),
                        json.loads(run('ip', '-j', 'neighbour', 'show', 'dev', extra['bridge'])),
                        allow_owned=has_live or has_saved)
    for name in run('virsh', 'list', '--all', '--name').splitlines():
        for state in ([], ['--inactive']):
            root = ET.fromstring(run('virsh', 'dumpxml', name, *state))
            if request['mode'] == 'clone' and isinstance(request.get('clone'), dict):
                target = request['clone'].get('disk', '')
                require(not any(node.get('file') and os.path.realpath(node.get('file')) == os.path.realpath(target)
                                for node in root.findall('./devices/disk/source')),
                        'No live or persistent domain may reference the selected unbooted copy.')
            if name != guest['route']['vm_name']:
                require(not any(node.get('address', '').lower() == extra['mac']
                                for node in root.findall('./devices/interface/mac')),
                        'The selected supplemental MAC belongs to another domain.')
    mode = request['mode']
    if mode == 'clone':
        clone = request['clone']
        require(has_live and has_saved and request['published']
                and isinstance(clone, dict) and set(clone) == {'vm_name', 'source', 'disk'}
                and clone['vm_name'] in request['owned_guests']
                and re.fullmatch(r'[a-z][a-z0-9-]{0,14}', clone['vm_name'])
                and clone['disk'] == '/opt/vms/win-' + clone['vm_name'] + '-clone.disk.qcow2'
                and isinstance(clone['source'], str) and clone['source'].startswith('/opt/')
                and clone['source'] != clone['disk'],
                'Clone only a selected Windows disk while its management NIC remains exact.')
        require(clone['vm_name'] not in run('virsh', 'list', '--all', '--name').splitlines(),
                'Never reuse or replace an existing domain.')
        source_stat = os.stat(clone['source'], follow_symlinks=False)
        image = json.loads(run('qemu-img', 'info', '--output=json', clone['source']))
        require(stat.S_ISREG(source_stat.st_mode) and image.get('format') == 'qcow2'
                and 'backing-filename' not in image, 'Use only the selected standalone regular golden image.')
        if os.path.lexists(clone['disk']):
            disk_stat = os.stat(clone['disk'], follow_symlinks=False)
            require(stat.S_ISREG(disk_stat.st_mode) and disk_stat.st_uid == 0 and disk_stat.st_nlink == 1,
                    'A leftover unbooted copy must be one root-owned regular file, never a link.')
            copied = json.loads(run('qemu-img', 'info', '--output=json', clone['disk']))
            require(copied.get('format') == 'qcow2' and 'backing-filename' not in copied
                    and not copied.get('snapshots') and copied.get('virtual-size', 0) > 0
                    and copied['virtual-size'] == image.get('virtual-size'),
                    'Reuse only a standalone unbooted copy with the original virtual capacity.')
            policy = json.loads(Path('/etc/hactarconfig/replacement-isolation.json').read_text())
            interfaces = request['owned_guests'][clone['vm_name']]['interfaces']
            require(not any(row.get('mac') == nic['mac'] or row.get('ipv4') == nic['address']
                            for field in ('https_clients', 'http_clients', 'released_clients', 'guest_host_clients')
                            for row in policy.get(field, []) for nic in interfaces),
                    'An unbooted copy must have no existing guest permissions.')
            run('qemu-img', 'compare', '-f', 'qcow2', '-F', 'qcow2', clone['source'], clone['disk'])
            return {'changed': False, 'created': False, 'busy': False}
        run('qemu-img', 'convert', '-f', 'qcow2', '-O', 'qcow2', '-S', '4k', clone['source'], clone['disk'])
        return {'changed': True, 'created': True, 'busy': False}
    if mode == 'ensure':
        if has_live or has_saved:
            if not request['published']:
                return {'changed': False, 'created': False, 'busy': True}
            require(has_live and has_saved, 'A published interface is absent from one native definition.')
            return {'changed': False, 'created': False, 'busy': False}
        require(not request['published'], 'A published interface is missing; refuse blind reconstruction.')
        xml = interface(extra)
        try:
            run('virsh', 'attach-device', guest['route']['vm_name'], '/dev/stdin', '--live', '--config', content=xml)
            require(inspect_domain(run('virsh', 'dumpxml', guest['route']['vm_name']), guest)
                    and inspect_domain(run('virsh', 'dumpxml', guest['route']['vm_name'], '--inactive'), guest),
                    'The exact NIC is not present in both native definitions.')
        except Exception:
            # This helper holds the native component lock throughout attach/readback/rollback.
            for state in ('--live', '--config'):
                current = run('virsh', 'dumpxml', guest['route']['vm_name'],
                              *(['--inactive'] if state == '--config' else []))
                if inspect_domain(current, guest):
                    run('virsh', 'detach-device', guest['route']['vm_name'], '/dev/stdin', state, content=xml)
            raise
        return {'changed': True, 'created': True, 'busy': False}
    if mode == 'inspect':
        require(request['published'] or not (has_live or has_saved),
                'Do not remove or adopt an unpublished existing interface.')
        return {'changed': False, 'created': False, 'present': has_live or has_saved, 'busy': False}
    require(not (has_live or has_saved) or request['published']
            or (mode == 'rollback' and request.get('job_created') is True),
            'Only a published component or this job\'s freshly proved unpublished creation may be removed.')
    if mode == 'rollback':
        require(not request['published'], 'Never roll back a durably owned interface.')
    owned = request['owned_guests']
    require(isinstance(owned, dict) and len(owned) == 5
            and all(re.fullmatch(r'[a-z][a-z0-9-]{0,14}', name) for name in owned),
            'Require all five selected Windows guest names before detaching their management NIC.')
    require(not set(owned).intersection(run('virsh', 'list', '--all', '--name').splitlines())
            and not any(os.path.lexists('/opt/vms/win-' + name + '-clone.disk.qcow2') for name in owned),
            'A selected Windows domain or clone disk still exists; retain its management connection.')
    if has_live or has_saved:
        for state, present in (('--live', has_live), ('--config', has_saved)):
            if present:
                run('virsh', 'detach-device', guest['route']['vm_name'], '/dev/stdin', state,
                    content=interface(extra))
    require(not inspect_domain(run('virsh', 'dumpxml', guest['route']['vm_name']), guest)
            and not inspect_domain(run('virsh', 'dumpxml', guest['route']['vm_name'], '--inactive'), guest),
            'The owned NIC remains in a native definition.')
    return {'changed': has_live or has_saved, 'created': False, 'present': False}


if __name__ == '__main__':
    data = json.load(sys.stdin)
    # Use the same per-hypervisor serialization boundary as network reservation operations.
    with open('/run/lock/aap-windows-management-interface.lock', 'a', encoding='utf-8') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        print(json.dumps(main(data)))
