# Purpose: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Manage one exact Windows-owned AAP Ethernet profile, preserving all others."""

import base64
import fcntl
import ipaddress
import json
from pathlib import Path
import subprocess
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def run(*args):
    return subprocess.check_output(list(args), text=True).strip()


def property_value(uuid, field):
    return run('nmcli', '--escape', 'no', '-g', field, 'connection', 'show', 'uuid', uuid)


def connection(uuid):
    fields = {'uuid': 'connection.uuid', 'name': 'connection.id', 'mac': '802-3-ethernet.mac-address',
              'addresses': 'ipv4.addresses', 'gateway': 'ipv4.gateway', 'dns': 'ipv4.dns',
              'never_default': 'ipv4.never-default', 'autoconnect': 'connection.autoconnect',
              'ipv4_method': 'ipv4.method', 'ipv4_ignore_auto_dns': 'ipv4.ignore-auto-dns',
              'ipv6_method': 'ipv6.method', 'ipv6_never_default': 'ipv6.never-default',
              'ipv6_ignore_auto_dns': 'ipv6.ignore-auto-dns'}
    values = {key: property_value(uuid, field) for key, field in fields.items()}
    values['mac'] = values['mac'].lower()
    for key in ('addresses', 'dns'):
        values[key] = [part.strip() for part in values[key].split(',') if part.strip()]
    for key in ('never_default', 'autoconnect', 'ipv4_ignore_auto_dns',
                'ipv6_never_default', 'ipv6_ignore_auto_dns'):
        require(values[key] in {'yes', 'no'}, 'NetworkManager returned an unexpected Boolean.')
        values[key] = values[key] == 'yes'
    return values


def snapshot():
    result = {}
    for uuid in run('nmcli', '-g', 'UUID', 'connection', 'show').splitlines():
        text = run('nmcli', '--escape', 'no', 'connection', 'show', 'uuid', uuid)
        # Keep every persistent setting, excluding only nmcli's active runtime groups.
        result[uuid] = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith(
            ('GENERAL.', 'IP4.', 'DHCP4.', 'IP6.', 'DHCP6.')))
    return result


def read_connections():
    result = []
    for uuid in run('nmcli', '-g', 'UUID', 'connection', 'show').splitlines():
        if property_value(uuid, 'connection.type') == '802-3-ethernet':
            result.append(connection(uuid))
    return result


def related(rows, extra):
    return [row for row in rows if row['uuid'] == extra['connection_uuid']
            or row['name'] == extra['connection_name'] or row['mac'] == extra['mac']
            or any(ipaddress.ip_interface(address).ip == ipaddress.ip_interface(extra['address']).ip
                   for address in row['addresses'])]


def exact(row, extra):
    return row == {'uuid': extra['connection_uuid'], 'name': extra['connection_name'], 'mac': extra['mac'],
                   'addresses': [extra['address']], 'gateway': '', 'dns': [],
                   'never_default': True, 'autoconnect': True, 'ipv4_method': 'manual',
                   'ipv4_ignore_auto_dns': True, 'ipv6_method': 'disabled',
                   'ipv6_never_default': True, 'ipv6_ignore_auto_dns': True}


def native(extra, present):
    links = json.loads(run('ip', '-j', 'address', 'show'))
    nics = [row for row in links if row.get('address', '').lower() == extra['mac']]
    if present:
        require(len(nics) == 1, 'The declared supplemental NIC was not observed in the AAP guest.')
        actual = [item['local'] + '/' + str(item['prefixlen']) for item in nics[0].get('addr_info', [])
                  if item.get('family') == 'inet']
        require(actual == [extra['address']], 'The observed supplemental IPv4 address is not exact.')
        require(not any(item.get('family') == 'inet6' for item in nics[0].get('addr_info', [])),
                'The supplemental NIC must not acquire IPv6 addresses.')
        for version in ('-4', '-6'):
            defaults = json.loads(run('ip', '-j', version, 'route', 'show', 'default'))
            require(not any(row.get('dev') == nics[0]['ifname'] for row in defaults),
                    'The supplemental NIC must never own an IPv4 or IPv6 default route.')
            routes = json.loads(run('ip', '-j', version, 'route', 'show', 'table', 'all'))
            own_routes = [row for row in routes if row.get('dev') == nics[0]['ifname']]
            require(version != '-6' or not own_routes, 'The disabled supplemental IPv6 stack must not own routes.')
            wanted = ipaddress.ip_interface(extra['address'])
            allowed = {str(wanted.network), str(wanted.ip), str(wanted.network.network_address),
                       str(wanted.network.broadcast_address)}
            require(all(row.get('dst', '').removesuffix('/32') in allowed
                        and row.get('protocol') == 'kernel'
                        and row.get('table', 'main') in ('main', 'local', 254, 255)
                        and row.get('type', 'unicast') in ('unicast', 'local', 'broadcast')
                        and not any(key in row for key in ('gateway', 'via', 'nexthops', 'nhid'))
                        for row in own_routes),
                    'The supplemental NIC may own only its directly connected kernel subnet/local routes.')
    else:
        require(not nics and not any(item.get('local') == str(ipaddress.ip_interface(extra['address']).ip)
                                    for row in links for item in row.get('addr_info', [])),
                'The supplemental NIC or address still exists after removal.')


def baseline(extra, machine_id):
    links = json.loads(run('ip', '-j', 'address', 'show'))
    addresses = sorted((row['ifname'], row.get('address', '').lower(), item['family'],
                        item['local'], item['prefixlen'])
                       for row in links if row.get('address', '').lower() != extra['mac']
                       for item in row.get('addr_info', []))
    routes = {}
    own_names = {row['ifname'] for row in links if row.get('address', '').lower() == extra['mac']}
    for version in ('-4', '-6'):
        # iproute2 reports an RA/DHCP lifetime as expires; its countdown is not a route change.
        rows = json.loads(run('ip', '-j', version, 'route', 'show', 'table', 'all'))
        routes[version] = sorted(({key: value for key, value in row.items() if key != 'expires'}
                                  for row in rows if row.get('dev') not in own_names),
                                 key=lambda row: json.dumps(row, sort_keys=True))
    return {'machine_id': machine_id, 'profiles': snapshot(), 'addresses': addresses,
            'routes': routes,
            'resolver': base64.b64encode(Path('/etc/resolv.conf').read_bytes()).decode()}


def preserved(before, after, extra):
    require(set(before) == set(after) and before['machine_id'] == after['machine_id'],
            'Use the authenticated pre-hotplug baseline from this same AAP guest.')
    for key in ('addresses', 'routes', 'resolver'):
        # JSON transports tuples as lists. Compare their canonical JSON representation.
        require(json.dumps(before[key], sort_keys=True) == json.dumps(after[key], sort_keys=True),
                'An existing address, default route or resolver changed since the pre-hotplug baseline.')
    own_uuid = extra['connection_uuid']
    require({key: value for key, value in before['profiles'].items() if key != own_uuid}
            == {key: value for key, value in after['profiles'].items() if key != own_uuid},
            'A foreign or automatic NetworkManager profile changed since the pre-hotplug baseline.')


def refuse_generic_profiles(rows, extra):
    links = json.loads(run('ip', '-j', 'address', 'show'))
    present = {row['ifname']: row.get('address', '').lower() for row in links}
    for row in rows:
        if row['uuid'] == extra['connection_uuid'] or not row['autoconnect'] or row['mac']:
            continue
        ifname = property_value(row['uuid'], 'connection.interface-name')
        require(ifname in present and present[ifname] and present[ifname] != extra['mac'],
                'An unbound autoconnect Ethernet profile could configure the future NIC; review it first.')


def main(request):
    guest = request['guest']
    extra = dict(guest['supplemental_interface'])
    extra['address'] += '/' + str(request['prefix_length'])
    machine_id = Path('/etc/machine-id').read_text().strip()
    require(machine_id == guest['guest_machine_id']
            and Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower() == guest['primary']['uuid'],
            'The authenticated AAP operating-system identity differs from the selected VM.')
    mode = request['mode']
    require(mode in {'capture', 'prepare', 'ensure', 'remove', 'read', 'rollback'}, 'Unsupported NetworkManager operation.')
    require(isinstance(request['published'], bool), 'Canonical ownership must be read before OS operations.')
    before = request.get('baseline') or baseline(extra, machine_id)
    preserved(before, baseline(extra, machine_id), extra)
    rows = read_connections()
    own = related(rows, extra)
    require(len(own) <= 1 and (not own or exact(own[0], extra)),
            'A foreign or partial NetworkManager profile conflicts with the declaration.')
    created = False
    if mode == 'prepare':
        if own and not request['published']:
            return {'changed': False, 'created': False, 'busy': True}
        refuse_generic_profiles(rows, extra)
        native(extra, request['published'])
        if own:
            require(request['published'], 'Refuse adopting an unpublished existing OS connection.')
        else:
            require(not request['published'], 'A published OS connection is missing; refuse blind reconstruction.')
            run('nmcli', 'connection', 'add', 'type', 'ethernet', 'ifname', '*',
                'con-name', extra['connection_name'], 'connection.uuid', extra['connection_uuid'],
                '802-3-ethernet.mac-address', extra['mac'], 'connection.autoconnect', 'yes',
                'ipv4.method', 'manual', 'ipv4.addresses', extra['address'],
                'ipv4.gateway', '', 'ipv4.dns', '', 'ipv4.never-default', 'yes',
                'ipv4.ignore-auto-dns', 'yes', 'ipv6.method', 'disabled',
                'ipv6.never-default', 'yes', 'ipv6.ignore-auto-dns', 'yes')
            created = True
        try:
            rows = read_connections()
            require(len(related(rows, extra)) == 1 and exact(related(rows, extra)[0], extra),
                    'The persistent OS connection differs from its declaration.')
            preserved(before, baseline(extra, machine_id), extra)
        except Exception:
            if created:
                # The NIC does not exist yet; deleting only this fresh profile cannot trigger DHCP.
                run('nmcli', 'connection', 'delete', 'uuid', extra['connection_uuid'])
            raise
    elif mode == 'ensure':
        require(request.get('baseline') is not None and len(own) == 1
                and (request['published'] or request.get('job_created') is True),
                'Create and prove the exact manual profile before attaching its NIC.')
        if request.get('job_created') is True:
            run('nmcli', '--wait', '30', 'connection', 'up', 'uuid', extra['connection_uuid'])
        rows = read_connections()
        native(extra, True)
    elif mode in {'remove', 'rollback'}:
        require(not own or request['published'] or (mode == 'rollback' and request.get('job_created') is True),
                'Remove only the exact published connection or this job\'s unpublished creation.')
        if mode == 'rollback':
            require(not request['published'], 'Never roll back a durable OS connection.')
        native(extra, False)
        if own:
            run('nmcli', 'connection', 'delete', 'uuid', extra['connection_uuid'])
        rows = read_connections()
        require(not related(rows, extra), 'The owned OS connection remains after removal.')
    elif mode == 'read':
        if guest['supplemental_state'] == 'present':
            require(len(own) == 1 and exact(own[0], extra), 'The recorded OS connection is missing.')
            native(extra, True)
        else:
            require(not own, 'The selected OS connection still exists.')
            native(extra, False)
    else:
        require(not own or request['published'],
                'Capture only a published existing profile; never adopt an unpublished connection.')
        links = json.loads(run('ip', '-j', 'address', 'show'))
        has_nic = any(row.get('address', '').lower() == extra['mac'] for row in links)
        native(extra, has_nic)
    preserved(before, baseline(extra, machine_id), extra)
    return {'changed': created or (mode == 'ensure' and request.get('job_created') is True)
            or (mode in {'remove', 'rollback'} and bool(own)), 'created': created,
            'busy': False, 'baseline': before,
            'connection_readback': {'machine_id': machine_id, 'connections': rows}}


if __name__ == '__main__':
    data = json.load(sys.stdin)
    with open('/run/lock/aap-windows-management-network.lock', 'a', encoding='utf-8') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        print(json.dumps(main(data)))
