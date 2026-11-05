# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Inspect exact instance-owned Windows clones without changing libvirt."""

import json
import fcntl
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


def unconfigured_permissions(guest, policy):
    """A native-only clone cannot substitute for missing managed provenance."""
    for field in ('https_clients', 'http_clients', 'released_clients', 'guest_host_clients'):
        for row in policy.get(field, []):
            if any(row['ipv4'] == nic['address'] or row['mac'] == nic['mac']
                   for nic in guest['interfaces']):
                raise ValueError('Managed guest permission exists; complete Windows ownership is required.')


def selected(record, domains, current, disk_exists):
    """Validate one live clone or complete absence; never recover orphan storage."""
    name = record['name']
    expected = record['guests'][name]
    saved = record['preview']
    if (saved.get('instance') != record['instance'] or saved.get('read_only') is not True
            or name not in saved.get('domains', {})):
        raise ValueError('Use the selected instance ownership preview captured before teardown.')
    prior = saved['domains'][name]
    disk = '/opt/vms/win-' + name + '-clone.disk.qcow2'
    if prior.get('disk') != disk or prior.get('interfaces') != expected['interfaces']:
        raise ValueError('The retained clone preview differs from the selected private profile.')
    if name not in domains:
        if disk_exists:
            raise ValueError('The domain is absent but storage remains; retained orphan recovery is not supported.')
        return {'present': False, 'guest': prior}
    owned = inspect(record['instance'], {name: expected}, domains)[name]
    if owned != prior or not disk_exists:
        raise ValueError('Actual native ownership no longer matches the original teardown preview.')
    if name in current and inspect(record['instance'], {name: expected}, current)[name] != owned:
        raise ValueError('Active and persistent clone ownership differ.')
    return {'present': True, 'guest': owned}


def main():
    record = json.load(sys.stdin)
    def virsh(*args):
        return subprocess.check_output(['virsh', '--readonly', '--connect', 'qemu:///system', *args], text=True).strip()
    domains = {name: virsh('dumpxml', name, '--inactive')
               for name in virsh('list', '--all', '--name').splitlines()}
    if record.get('mode') in ('selected', 'remove'):
        name = record['name']
        disk = Path('/opt/vms/win-' + name + '-clone.disk.qcow2')
        exists = disk.exists() or disk.is_symlink()
        if exists and (not disk.is_file() or disk.is_symlink() or disk.stat().st_nlink != 1):
            raise ValueError('Expected one regular non-symlink Windows clone disk.')
        current = dict(domains)
        if name in virsh('list', '--name').splitlines():
            current[name] = virsh('dumpxml', name)
        result = selected(record, domains, current, exists)
        result['active'] = name in virsh('list', '--name').splitlines()
        result['nvram'] = ET.fromstring(domains[name]).findtext('./os/nvram') if result['present'] else None
        if result['nvram'] and result['nvram'] not in (
                '/var/lib/libvirt/qemu/nvram/' + name + '_VARS.fd',
                '/var/lib/libvirt/qemu/nvram/' + name + '_VARS.qcow2'):
            raise ValueError('The selected clone has nonstandard NVRAM; explicit review is required.')
        if result['present'] and virsh('snapshot-list', name, '--name'):
            raise ValueError('A selected clone has snapshots; explicit review is required.')
        if record.get('unconfigured') is True:
            policy = json.loads(Path('/etc/hactarconfig/replacement-isolation.json').read_text())
            if policy != record['policy']:
                raise ValueError('Actual recovery policy differs from authenticated source policy.')
            unconfigured_permissions(record['guests'][name], policy)
            subprocess.run(['/usr/local/sbin/hactar-recovery-isolation', 'check'],
                           input=json.dumps(policy), text=True, check=True, capture_output=True)
            for options in ([], ['--permanent']):
                rules = subprocess.check_output(['firewall-cmd', *options, '--list-all-zones'], text=True)
                if any(re.search(r'\bsource\s+address="' + re.escape(nic['address']) + r'(?:/32)?"', rules)
                       for nic in record['guests'][name]['interfaces']):
                    raise ValueError('A selected native host permission requires managed ownership cleanup.')
        result['changed'] = False
        if record['mode'] == 'remove' and result['present']:
            identity = disk.stat()
            if result['active']:
                subprocess.run(['virsh', 'destroy', name], check=True, capture_output=True)
            info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(disk)], text=True))
            if info.get('format') != 'qcow2' or 'backing-filename' in info:
                raise ValueError('Only a standalone qcow2 clone can be removed.')
            subprocess.run(['virsh', 'undefine', name] + (['--nvram'] if result['nvram'] else []),
                           check=True, capture_output=True)
            after = disk.stat(follow_symlinks=False)
            if (after.st_dev, after.st_ino, after.st_nlink) != (identity.st_dev, identity.st_ino, 1):
                raise ValueError('The clone disk identity changed during removal; storage was preserved.')
            disk.unlink()
            if name in virsh('list', '--all', '--name').splitlines() or disk.exists():
                raise ValueError('The exact guest removal did not complete.')
            result['changed'] = True
        print(json.dumps(result))
        return
    owned = inspect(record['instance'], record['guests'], domains)
    for name, guest in owned.items():
        metadata = os.stat(guest['disk'], follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or Path(guest['disk']).is_symlink():
            raise ValueError('Expected a regular, non-symlinked owned clone disk.')
        if virsh('snapshot-list', name, '--name'):
            raise ValueError('A selected guest has snapshots; explicit review is required.')
    print(json.dumps({'instance': record['instance'], 'domains': owned, 'read_only': True}))


if __name__ == '__main__':
    # Existing Windows clone/network operations use this same native boundary.
    with open('/run/lock/aap-windows-management-interface.lock', 'a', encoding='utf-8') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        main()
