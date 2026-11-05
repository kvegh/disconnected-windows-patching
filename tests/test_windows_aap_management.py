# Exercise actual native parsers and operation boundaries; see tests/README.md.
"""Prove bounded second-NIC and persistent-connection behavior without hosts."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from ansible.errors import AnsibleFilterError
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.template import Templar
import yaml


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


management = load('windows_management', ROOT / 'filter_plugins/windows_aap_management.py')
native = load('windows_aap_interface', ROOT / 'assets/windows-aap-interface.py')
nm = load('windows_aap_nm', ROOT / 'assets/windows-aap-networkmanager.py')
UUID = '11111111-2222-4333-8444-555555555555'
NM_UUID = '22222222-3333-4444-8555-666666666666'
MACHINE = '123456789abcdef0123456789abcdef0'
HYPERVISOR = '23456789abcdef0123456789abcdef01'


def declaration():
    return {'owner_project_id': 'disconnected-windows-patching', 'network': 'example-isolated',
            'bridge': 'virbr42', 'address': '10.42.0.16', 'mac': '52:54:00:00:00:16',
            'connection_uuid': NM_UUID, 'connection_name': 'example-windows-management',
            'attachment_created': True, 'connection_created': True}


def profile():
    pin = {'machine_id': HYPERVISOR, 'isolation_bridges': ['virbr1', 'virbr42']}
    primary = {'uuid': UUID, 'disk': '/opt/vms/example-aap.disk.qcow2', 'address': '10.23.0.100',
               'mac': '52:54:00:00:01:01', 'network': 'example-internal', 'bridge': 'virbr1',
               'verified': True, 'hypervisor_machine_id': HYPERVISOR}
    return {'route': {'vm_name': 'example-aap', 'vm_ip': primary['address'],
                      'aap_hostname': 'https://example-aap.example.test', 'hypervisor': pin,
                      'guest_host_keys': ['ssh-ed25519 example']},
            'primary': primary, 'interface': declaration(), 'prefix_length': 24}


def guest(state='present'):
    data = profile()
    return {'kind': 'aap', 'route': data['route'], 'primary': data['primary'],
            'guest_machine_id': MACHINE, 'supplemental_interface': data['interface'],
            'supplemental_state': state, 'connection_readback': {}}


def domain(extra=False):
    data = profile()
    primary = data['primary']
    additional = native.interface(data['interface']) if extra else ''
    return ('<domain><name>example-aap</name><uuid>' + UUID + '</uuid><devices>'
            '<disk type="file" device="disk"><source file="' + primary['disk'] + '"/></disk>'
            '<interface type="network"><mac address="' + primary['mac'] + '"/>'
            '<source network="' + primary['network'] + '"/><model type="virtio"/></interface>'
            + additional + '</devices></domain>')


NETWORK = ('<network><name>example-isolated</name><bridge name="virbr42"/>'
           '<ip address="10.42.0.1" prefix="24"><dhcp>'
           '<range start="10.42.0.100" end="10.42.0.200"/>'
           '</dhcp></ip></network>')


class ProfileAndPreservationTests(unittest.TestCase):
    def test_profile_preserves_exact_existing_primary_and_direct_isolated_reachability(self):
        data = profile()
        guests = {'example-win': {'interfaces': [{'network': 'example-isolated',
                  'mac': '52:54:00:00:00:30', 'address': '10.42.0.30'}]}}
        self.assertEqual(management.profile(data, 'example-aap', data['route']['hypervisor'], guests), data)

    def test_wrong_owner_primary_route_pin_or_shared_identity_is_refused(self):
        for location, key, value in [
            ('route', 'vm_name', 'another-aap'), ('primary', 'verified', False),
            ('primary', 'disk', '/opt/vms/foreign.disk.qcow2'),
            ('interface', 'owner_project_id', 'another-project'),
            ('interface', 'attachment_created', False), ('interface', 'connection_created', False),
            ('interface', 'network', 'example-internal'), ('interface', 'bridge', 'foreign-bridge'),
            ('interface', 'mac', 'ff:ff:ff:ff:ff:ff'), ('interface', 'address', '8.8.8.8'),
            ('interface', 'connection_uuid', 'not-a-uuid'),
        ]:
            data = profile()
            data[location][key] = value
            with self.subTest(key=key, value=value), self.assertRaises((AnsibleFilterError, ValueError)):
                management.profile(data, 'example-aap', profile()['route']['hypervisor'], {})

    def test_selected_windows_address_and_mac_collisions_are_refused(self):
        for key in ['address', 'mac']:
            data = profile()
            nic = {'network': 'example-isolated', 'mac': '52:54:00:00:00:30', 'address': '10.42.0.30'}
            nic[key] = data['interface'][key]
            with self.subTest(key=key), self.assertRaises(AnsibleFilterError):
                management.profile(data, 'example-aap', data['route']['hypervisor'], {'win': {'interfaces': [nic]}})

    def test_teardown_accepts_only_exact_owned_nic_removal(self):
        self.assertTrue(management.preserved_definition(domain(), domain(True), profile()))
        self.assertTrue(management.preserved_definition(domain(True), domain(), profile()))
        self.assertTrue(management.preserved_definition(domain(True), domain(True), profile()))
        for changed in [domain().replace(UUID, NM_UUID), domain().replace('example-internal', 'foreign'),
                        domain().replace('</devices>', '<controller type="usb"/></devices>')]:
            with self.subTest(changed=changed), self.assertRaises(AnsibleFilterError):
                management.preserved_definition(changed, domain(True), profile())

    def test_existing_ssh_credential_must_pin_exact_selected_guest_keys_at_its_address(self):
        route = profile()['route']
        self.assertTrue(management.ssh_trust(route['vm_ip'] + ' ssh-ed25519 example\n', route))
        for value in ['another.example.test ssh-ed25519 example\n',
                      route['vm_ip'] + ' ssh-ed25519 foreign\n',
                      '@cert-authority * ssh-ed25519 example\n']:
            with self.subTest(value=value), self.assertRaises(AnsibleFilterError):
                management.ssh_trust(value, route)


class NativeTopologyTests(unittest.TestCase):
    def test_only_primary_plus_the_exact_marked_supplemental_nic_are_allowed(self):
        self.assertFalse(native.inspect_domain(domain(), guest()))
        self.assertTrue(native.inspect_domain(domain(True), guest()))
        for changed in [domain(True).replace('ua-windows-', 'foreign-'),
                        domain(True).replace(UUID, NM_UUID, 1),
                        domain(True).replace('example-internal', 'another-network'),
                        domain(True).replace('</devices>', native.interface(declaration()) + '</devices>'),
                        domain(True).replace('/opt/vms/example-aap.disk.qcow2', '/opt/vms/foreign')]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                native.inspect_domain(changed, guest())

    def test_static_address_must_be_unused_and_outside_existing_dhcp_pool(self):
        extra = dict(declaration(), address='10.42.0.16/24')
        native.inspect_network(NETWORK, extra, [], '', [])
        cases = [
            (NETWORK.replace('<bridge', '<forward mode="nat"/><bridge'), [], '', []),
            (NETWORK.replace('virbr42', 'another-bridge'), [], '', []),
            (NETWORK.replace('<range', '<host ip="10.42.0.16" mac="52:54:00:01:01:01"/><range'), [], '', []),
            (NETWORK.replace('start="10.42.0.100"', 'start="10.42.0.2"'), [], '', []),
            (NETWORK, [{'addr_info': [{'local': '10.42.0.16'}]}], '', []),
            (NETWORK, [], 'header\nseparator\nnow 52:54:00:01:01:01 52:54:00:01:01:01 ipv4 10.42.0.16/24', []),
            (NETWORK, [], '', [{'dst': '10.42.0.16', 'lladdr': extra['mac']}]),
        ]
        for xml, addresses, leases, neighbours in cases:
            with self.subTest(xml=xml, addresses=addresses, leases=leases, neighbours=neighbours), self.assertRaises(ValueError):
                native.inspect_network(xml, extra, addresses, leases, neighbours)

    def test_existing_owned_neighbour_requires_exact_mac_and_native_ownership(self):
        extra = dict(declaration(), address='10.42.0.16/24')
        own = [{'dst': '10.42.0.16', 'lladdr': extra['mac']}]
        native.inspect_network(NETWORK, extra, [], '', own, allow_owned=True)
        with self.assertRaises(ValueError):
            native.inspect_network(NETWORK, extra, [], '', [{'dst': '10.42.0.16', 'lladdr': '52:54:00:00:00:99'}], True)


class NativeFiles:
    policy = {}

    def __init__(self, path):
        self.path = path

    def read_text(self):
        if self.path == '/etc/hactarconfig/replacement-isolation.json':
            return json.dumps(self.policy)
        return HYPERVISOR


class LibvirtFixture:
    def __init__(self, present=False):
        self.live = domain(present)
        self.saved = domain(present)
        self.writes = []
        self.partial_attach_failure = False
        self.foreign = False
        self.disks = set()
        self.pristine = True
        self.disk_reference = False

    def run(self, *args, content=None):
        if args == ('virsh', 'domstate', 'example-aap'):
            return 'running'
        if args[:3] == ('virsh', 'dumpxml', 'example-aap'):
            return self.saved if '--inactive' in args else self.live
        if args[:2] == ('virsh', 'net-dumpxml'):
            return NETWORK
        if args == ('ip', '-j', '-4', 'address', 'show') or args[:3] == ('ip', '-j', 'neighbour'):
            return '[]'
        if args[:2] == ('virsh', 'net-dhcp-leases'):
            return 'header\nseparator'
        if args == ('virsh', 'list', '--all', '--name'):
            return 'example-aap\nforeign' if self.foreign or self.disk_reference else 'example-aap'
        if args[:3] == ('virsh', 'dumpxml', 'foreign'):
            if self.disk_reference:
                return domain().replace('<name>example-aap</name>', '<name>foreign</name>').replace(
                    '/opt/vms/example-aap.disk.qcow2', '/opt/vms/win-example-ext-clone.disk.qcow2')
            return domain(True).replace('<name>example-aap</name>', '<name>foreign</name>')
        if args[:2] == ('virsh', 'attach-device'):
            self.writes.append(args)
            self.live = domain(True)
            if self.partial_attach_failure:
                raise RuntimeError('synthetic persistent attach failure')
            self.saved = domain(True)
            return ''
        if args[:2] == ('virsh', 'detach-device'):
            self.writes.append(args)
            if '--live' in args:
                self.live = domain()
            if '--config' in args:
                self.saved = domain()
            return ''
        if args[:2] == ('qemu-img', 'info'):
            return '{"format":"qcow2","virtual-size":4096}'
        if args[:2] == ('qemu-img', 'compare'):
            if not self.pristine:
                raise ValueError('The copy differs from the original golden.')
            return ''
        if args[:2] == ('qemu-img', 'convert'):
            self.writes.append(args)
            self.disks.add(args[-1])
            return ''
        raise AssertionError(args)


class LibvirtOperationTests(unittest.TestCase):
    def execute(self, fixture, mode='ensure', published=False, job_created=False, clone=None):
        with patch.object(native, 'run', fixture.run), patch.object(native, 'Path', NativeFiles), \
                patch.object(native.os.path, 'lexists', lambda path: path in fixture.disks), \
                patch.object(native.os, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_uid=0, st_nlink=1)):
            return native.main({'guest': guest(), 'mode': mode, 'prefix_length': 24,
                                'owned_guests': {name: {'interfaces': [{'mac': '52:54:00:00:02:%02x' % index,
                                                                      'address': '10.42.0.%d' % (20 + index)}]}
                                                for index, name in enumerate(['example-ext', 'example-int', 'example-win22',
                                                                              'example-win25', 'example-ad'])},
                                'clone': clone, 'published': published, 'job_created': job_created})

    def test_exact_new_attachment_changes_only_the_supplemental_device(self):
        fixture = LibvirtFixture()
        result = self.execute(fixture)
        self.assertTrue(result['created'])
        self.assertTrue(management.preserved_definition(domain(), fixture.saved, profile()))
        self.assertTrue(native.inspect_domain(fixture.live, guest()))
        self.assertEqual(len(fixture.writes), 1)
        self.assertEqual(fixture.writes[0][:2], ('virsh', 'attach-device'))

    def test_simultaneous_unpublished_match_waits_without_adoption_or_mutation(self):
        fixture = LibvirtFixture(True)
        result = self.execute(fixture)
        self.assertTrue(result['busy'])
        self.assertFalse(result['created'])
        self.assertEqual(fixture.writes, [])

    def test_identical_published_retry_is_read_only(self):
        fixture = LibvirtFixture(True)
        self.assertFalse(self.execute(fixture, published=True)['changed'])
        self.assertEqual(fixture.writes, [])

    def test_foreign_domain_mac_and_unmarked_interface_are_refused(self):
        fixture = LibvirtFixture()
        fixture.foreign = True
        with self.assertRaises(ValueError):
            self.execute(fixture)
        self.assertEqual(fixture.writes, [])
        fixture = LibvirtFixture(True)
        fixture.saved = fixture.saved.replace('ua-windows-', 'foreign-')
        with self.assertRaises(ValueError):
            self.execute(fixture, published=True)
        self.assertEqual(fixture.writes, [])

    def test_partial_attach_failure_rolls_back_only_its_component_under_native_lock(self):
        fixture = LibvirtFixture()
        fixture.partial_attach_failure = True
        with self.assertRaises(RuntimeError):
            self.execute(fixture)
        self.assertEqual((fixture.live, fixture.saved), (domain(), domain()))
        self.assertEqual([row[1] for row in fixture.writes], ['attach-device', 'detach-device'])

    def test_missing_published_nic_is_not_blindly_reconstructed(self):
        fixture = LibvirtFixture()
        with self.assertRaises(ValueError):
            self.execute(fixture, published=True)
        self.assertEqual(fixture.writes, [])

    def test_rollback_needs_actual_creation_and_never_removes_durable_nic(self):
        fixture = LibvirtFixture(True)
        for published, created in [(False, False), (True, True)]:
            with self.subTest(published=published, created=created), self.assertRaises(ValueError):
                self.execute(fixture, mode='rollback', published=published, job_created=created)
        self.assertEqual(fixture.writes, [])
        self.assertTrue(self.execute(fixture, mode='rollback', job_created=True)['changed'])
        self.assertEqual((fixture.live, fixture.saved), (domain(), domain()))

    def test_clone_wins_then_detach_refuses_the_new_owned_disk(self):
        fixture = LibvirtFixture(True)
        clone = {'vm_name': 'example-ext', 'source': '/opt/images/example.qcow2',
                 'disk': '/opt/vms/win-example-ext-clone.disk.qcow2'}
        self.execute(fixture, published=True)  # An earlier no-op ensure provides no long-lived lease.
        self.execute(fixture, mode='clone', published=True, clone=clone)
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='remove', published=True)
        self.assertTrue(native.inspect_domain(fixture.live, guest()))
        self.assertEqual(len(fixture.disks), 1)

    def test_only_an_unreferenced_pristine_copy_without_permissions_can_be_reused(self):
        clone = {'vm_name': 'example-ext', 'source': '/opt/images/example.qcow2',
                 'disk': '/opt/vms/win-example-ext-clone.disk.qcow2'}
        fixture = LibvirtFixture(True)
        fixture.disks.add(clone['disk'])
        result = self.execute(fixture, mode='clone', published=True, clone=clone)
        self.assertFalse(result['created'])
        self.assertFalse(result['changed'])
        self.assertEqual(fixture.writes, [])
        fixture.pristine = False
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='clone', published=True, clone=clone)
        fixture.pristine = True
        fixture.disk_reference = True
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='clone', published=True, clone=clone)
        fixture.disk_reference = False
        with patch.object(NativeFiles, 'policy', {'released_clients': [{'mac': '52:54:00:00:02:00', 'ipv4': '10.42.0.20'}]}):
            with self.assertRaises(ValueError):
                self.execute(fixture, mode='clone', published=True, clone=clone)

    def test_detach_wins_then_clone_refuses_before_any_disk_write(self):
        fixture = LibvirtFixture(True)
        clone = {'vm_name': 'example-ext', 'source': '/opt/images/example.qcow2',
                 'disk': '/opt/vms/win-example-ext-clone.disk.qcow2'}
        self.execute(fixture, published=True)
        self.execute(fixture, mode='remove', published=True)
        writes = list(fixture.writes)
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='clone', published=True, clone=clone)
        self.assertEqual(fixture.writes, writes)
        self.assertEqual(fixture.disks, set())


class FileFixture:
    def __init__(self, path):
        self.path = path

    def read_text(self):
        return UUID if 'product_uuid' in self.path else MACHINE

    def read_bytes(self):
        return b'unchanged-resolver'


class NetworkManagerFixture:
    def __init__(self):
        self.primary_uuid = '33333333-4444-4555-8666-777777777777'
        self.rows = {self.primary_uuid: {'connection.uuid': self.primary_uuid, 'connection.id': 'primary',
                     'connection.type': '802-3-ethernet', '802-3-ethernet.mac-address': '52:54:00:00:01:01',
                     'ipv4.addresses': '10.23.0.100/24', 'ipv4.gateway': '10.23.0.1',
                     'ipv4.dns': '10.23.0.1', 'ipv4.never-default': 'no', 'connection.autoconnect': 'yes',
                     'ipv4.method': 'auto', 'ipv4.ignore-auto-dns': 'no', 'ipv6.method': 'auto',
                     'ipv6.never-default': 'no', 'ipv6.ignore-auto-dns': 'no', 'connection.interface-name': 'eth0'}}
        self.nic_present = True
        self.up_failure = False
        self.writes = []
        self.ipv6_address = False
        self.ipv6_default = False
        self.expiry = 100
        self.primary_address = '10.23.0.100'
        self.primary_gateway = '10.23.0.1'
        self.supplemental_address = '10.42.0.16'
        self.resolver = b'unchanged-resolver'
        self.extra_route = False

    def install_owned(self):
        extra = declaration()
        self.rows[NM_UUID] = {'connection.uuid': NM_UUID, 'connection.id': extra['connection_name'],
                             'connection.type': '802-3-ethernet', '802-3-ethernet.mac-address': extra['mac'],
                             'ipv4.addresses': extra['address'] + '/24', 'ipv4.gateway': '', 'ipv4.dns': '',
                             'ipv4.never-default': 'yes', 'connection.autoconnect': 'yes',
                             'ipv4.method': 'manual', 'ipv4.ignore-auto-dns': 'yes', 'ipv6.method': 'disabled',
                             'ipv6.never-default': 'yes', 'ipv6.ignore-auto-dns': 'yes'}

    def run(self, *args):
        if args == ('ip', '-j', '-4', 'route', 'show', 'default'):
            self.expiry -= 1
            return json.dumps([{'dst': 'default', 'dev': 'eth0', 'gateway': self.primary_gateway,
                                'metric': 100, 'table': 'main', 'expires': self.expiry}])
        if args == ('ip', '-j', '-6', 'route', 'show', 'default'):
            return '[{"dst":"default","dev":"eth1"}]' if self.ipv6_default else '[]'
        if args == ('ip', '-j', '-4', 'route', 'show', 'table', 'all'):
            rows = json.loads(self.run('ip', '-j', '-4', 'route', 'show', 'default'))
            rows += [{'dst': '10.42.0.0/24', 'dev': 'eth1', 'protocol': 'kernel'}] if self.nic_present else []
            if self.extra_route:
                rows += [{'dst': '203.0.113.5', 'dev': 'eth1', 'protocol': 'static'}]
            return json.dumps(rows)
        if args == ('ip', '-j', '-6', 'route', 'show', 'table', 'all'):
            return self.run('ip', '-j', '-6', 'route', 'show', 'default')
        if args == ('ip', '-j', 'address', 'show'):
            return json.dumps([{'ifname': 'eth0', 'address': '52:54:00:00:01:01', 'addr_info': [
                {'family': 'inet', 'local': self.primary_address, 'prefixlen': 24,
                 'valid_life_time': self.expiry, 'preferred_life_time': self.expiry}]}] +
                ([{'ifname': 'eth1', 'address': declaration()['mac'],
                                'addr_info': [{'family': 'inet', 'local': self.supplemental_address, 'prefixlen': 24}]
                                + ([{'family': 'inet6', 'local': 'fe80::16', 'prefixlen': 64}]
                                   if self.ipv6_address else [])}]
                              if self.nic_present else []))
        if args == ('nmcli', '-g', 'UUID', 'connection', 'show'):
            return '\n'.join(self.rows)
        if args[:4] == ('nmcli', '--escape', 'no', '-g'):
            return self.rows[args[-1]][args[4]]
        if args[:5] == ('nmcli', '--escape', 'no', 'connection', 'show'):
            return json.dumps(self.rows[args[-1]], sort_keys=True)
        if args[:3] == ('nmcli', 'connection', 'add'):
            self.writes.append(args)
            self.install_owned()
            return ''
        if args[:5] == ('nmcli', '--wait', '30', 'connection', 'up'):
            self.writes.append(args)
            if self.up_failure:
                raise RuntimeError('synthetic activation failure')
            return ''
        if args[:3] == ('nmcli', 'connection', 'delete'):
            self.writes.append(args)
            del self.rows[args[-1]]
            return ''
        raise AssertionError(args)


class NetworkManagerOperationTests(unittest.TestCase):
    def execute(self, fixture, mode='prepare', published=False, job_created=False, state='present', baseline=None):
        with patch.object(nm, 'run', fixture.run), patch.object(nm, 'Path', FileFixture), \
                patch.object(FileFixture, 'read_bytes', lambda _: fixture.resolver):
            return nm.main({'guest': guest(state), 'mode': mode, 'prefix_length': 24,
                            'published': published, 'job_created': job_created, 'baseline': baseline})

    def test_new_exact_profile_uses_mac_binding_static_address_no_gateway_or_dns(self):
        fixture = NetworkManagerFixture()
        fixture.nic_present = False
        primary = copy.deepcopy(fixture.rows[fixture.primary_uuid])
        result = self.execute(fixture)
        self.assertTrue(result['created'])
        self.assertTrue(nm.exact(result['connection_readback']['connections'][-1],
                                dict(declaration(), address='10.42.0.16/24')))
        self.assertEqual(primary, fixture.rows[fixture.primary_uuid])
        self.assertIn('ipv6.method', fixture.writes[0])
        self.assertIn('disabled', fixture.writes[0])

    def test_exact_published_retry_performs_no_nm_writes(self):
        fixture = NetworkManagerFixture()
        fixture.install_owned()
        self.assertFalse(self.execute(fixture, published=True)['changed'])
        self.assertEqual(fixture.writes, [])

    def test_unpublished_existing_or_foreign_connection_is_not_adopted(self):
        for foreign in (False, True):
            fixture = NetworkManagerFixture()
            fixture.install_owned()
            if foreign:
                fixture.rows[NM_UUID]['connection.id'] = 'foreign'
            if foreign:
                with self.assertRaises(ValueError):
                    self.execute(fixture, published=True)
            else:
                self.assertTrue(self.execute(fixture)['busy'])
            self.assertEqual(fixture.writes, [])

    def test_missing_published_connection_is_not_blindly_reconstructed(self):
        fixture = NetworkManagerFixture()
        with self.assertRaises(ValueError):
            self.execute(fixture, published=True)
        self.assertEqual(fixture.writes, [])

    def test_failed_activation_keeps_profile_until_owned_nic_is_detached(self):
        fixture = NetworkManagerFixture()
        fixture.nic_present = False
        before = copy.deepcopy(fixture.rows)
        prepared = self.execute(fixture)
        fixture.nic_present = True
        fixture.up_failure = True
        with self.assertRaises(RuntimeError):
            self.execute(fixture, mode='ensure', job_created=True, baseline=prepared['baseline'])
        self.assertIn(NM_UUID, fixture.rows)
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='rollback', job_created=True, baseline=prepared['baseline'])
        fixture.nic_present = False
        self.execute(fixture, mode='rollback', job_created=True, baseline=prepared['baseline'])
        self.assertEqual(fixture.rows, before)
        self.assertEqual(fixture.writes[-1][:3], ('nmcli', 'connection', 'delete'))

    def test_cleanup_and_absent_retry_preserve_the_primary(self):
        fixture = NetworkManagerFixture()
        before = copy.deepcopy(fixture.rows)
        fixture.install_owned()
        fixture.nic_present = False
        self.assertTrue(self.execute(fixture, mode='remove', published=True, state='absent')['changed'])
        self.assertEqual(fixture.rows, before)
        fixture.nic_present = False
        self.assertFalse(self.execute(fixture, mode='read', state='absent')['changed'])
        self.assertFalse(self.execute(fixture, mode='remove', state='absent')['changed'])

    def test_unpublished_profile_rollback_requires_this_jobs_actual_creation(self):
        fixture = NetworkManagerFixture()
        fixture.install_owned()
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='rollback', job_created=False)
        fixture.nic_present = False
        self.assertTrue(self.execute(fixture, mode='rollback', job_created=True)['changed'])

    def test_durable_profile_is_never_rolled_back(self):
        fixture = NetworkManagerFixture()
        fixture.install_owned()
        with self.assertRaises(ValueError):
            self.execute(fixture, mode='rollback', published=True, job_created=True)
        self.assertEqual(fixture.writes, [])

    def test_published_ipv4_ipv6_or_auto_dns_drift_is_refused_without_repair(self):
        for key, value in [('ipv4.method', 'auto'), ('ipv4.ignore-auto-dns', 'no'),
                           ('ipv6.method', 'auto'), ('ipv6.never-default', 'no'),
                           ('ipv6.ignore-auto-dns', 'no'), ('ipv4.never-default', 'no')]:
            fixture = NetworkManagerFixture()
            fixture.install_owned()
            fixture.rows[NM_UUID][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.execute(fixture, published=True)
            self.assertEqual(fixture.writes, [])

    def test_observed_ipv6_address_or_ipv6_default_route_refuses_publication(self):
        for key in ['ipv6_address', 'ipv6_default']:
            fixture = NetworkManagerFixture()
            fixture.install_owned()
            setattr(fixture, key, True)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.execute(fixture, mode='read', published=True)
            self.assertEqual(fixture.writes, [])

    def test_precreated_profile_activates_without_changing_primary_despite_lifetime_countdown(self):
        fixture = NetworkManagerFixture()
        fixture.nic_present = False
        prepared = self.execute(fixture)
        fixture.nic_present = True
        result = self.execute(fixture, mode='ensure', job_created=True, baseline=prepared['baseline'])
        self.assertFalse(result['busy'])
        self.assertLess(fixture.expiry, 100)
        self.assertEqual(result['connection_readback']['connections'][-1]['ipv4_method'], 'manual')

    def test_eligible_foreign_autoconnect_profile_refuses_hotplug_preparation(self):
        fixture = NetworkManagerFixture()
        fixture.nic_present = False
        fixture.rows[fixture.primary_uuid]['802-3-ethernet.mac-address'] = ''
        fixture.rows[fixture.primary_uuid]['connection.interface-name'] = ''
        with self.assertRaises(ValueError):
            self.execute(fixture)
        self.assertEqual(fixture.writes, [])

    def test_post_hotplug_automatic_profile_route_or_primary_address_drift_is_detected(self):
        for kind in ('profile', 'route', 'address', 'dns'):
            fixture = NetworkManagerFixture()
            fixture.nic_present = False
            prepared = self.execute(fixture)
            fixture.nic_present = True
            if kind == 'profile':
                fixture.rows['44444444-5555-4666-8777-888888888888'] = copy.deepcopy(fixture.rows[fixture.primary_uuid])
            elif kind == 'route':
                fixture.primary_gateway = '10.23.0.254'
            elif kind == 'address':
                fixture.primary_address = '10.23.0.101'
            else:
                fixture.resolver = b'foreign-resolver'
            writes = list(fixture.writes)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.execute(fixture, mode='ensure', job_created=True, baseline=prepared['baseline'])
            self.assertEqual(fixture.writes, writes)

    def test_cleanup_capture_refuses_extra_address_ipv6_or_default_route_drift(self):
        for key, value in [('supplemental_address', '10.42.0.99'), ('ipv6_address', True),
                           ('ipv6_default', True), ('extra_route', True)]:
            fixture = NetworkManagerFixture()
            fixture.install_owned()
            setattr(fixture, key, value)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.execute(fixture, mode='capture', published=True, state='absent')
            self.assertEqual(fixture.writes, [])

    def test_cleanup_capture_supports_exact_profile_after_interrupted_detach(self):
        fixture = NetworkManagerFixture()
        fixture.install_owned()
        fixture.nic_present = False
        captured = self.execute(fixture, mode='capture', published=True, state='absent')
        self.assertEqual(fixture.writes, [])
        result = self.execute(fixture, mode='remove', published=True, state='absent', baseline=captured['baseline'])
        self.assertTrue(result['changed'])
        self.assertNotIn(NM_UUID, fixture.rows)


class NativeAnsibleGuardTests(unittest.TestCase):
    def condition(self, expressions, values):
        loader = DataLoader()
        guard = Conditional(loader=loader)
        guard.when = expressions
        return guard.evaluate_conditional(Templar(loader=loader, variables=values), values)

    def test_rollback_requires_fresh_canonical_absence_not_only_own_publish_flag(self):
        tasks = yaml.safe_load((ROOT / 'tasks/windows_aap_management_network.yml').read_text())
        transaction = next(row for row in tasks[0]['block'] if row.get('rescue'))
        task = next(row for row in transaction['rescue'] if 'Undo only' in row['name'])
        values = {'windows_aap_management_state': 'present', 'windows_aap_network_canonical_refreshed': True,
                  '__recovery_release_plan': {'canonical_resource_absent': True,
                                             'canonical_resource_present': False, 'durable_ownership_published': False}}
        self.assertTrue(self.condition(task['when'], values))
        for field, value in [('canonical_resource_present', True), ('canonical_resource_absent', False),
                             ('durable_ownership_published', True)]:
            changed = copy.deepcopy(values)
            changed['__recovery_release_plan'][field] = value
            self.assertFalse(self.condition(task['when'], changed))
        self.assertFalse(self.condition(task['when'], dict(values, windows_aap_network_canonical_refreshed=False)))

    def test_optional_settings_absent_preserve_the_existing_infrastructure_path(self):
        tasks = yaml.safe_load((ROOT / '01-win-vm-setup.yml').read_text())[0]['tasks']
        task = next(row for row in tasks if row.get('ansible.builtin.include_tasks')
                    == 'tasks/windows_aap_management_network.yml')
        self.assertFalse(self.condition([task['when']], {}))
        self.assertTrue(self.condition([task['when']], {'windows_runtime_aap_management': {}}))

    def test_network_transaction_rejects_unreviewed_shared_code_before_checkout(self):
        outer = yaml.safe_load((ROOT / 'tasks/windows_aap_management_network.yml').read_text())[0]
        transaction = next(row for row in outer['block'] if row.get('rescue'))
        guard = next(row for row in transaction['block'] if row['name'].startswith('Require the same fixed public source'))
        dependency = yaml.safe_load((ROOT / 'roles/windows_recovery_release/defaults/main.yml').read_text())
        self.assertTrue(self.condition(guard['ansible.builtin.assert']['that'],
                                       {'windows_aap_network_dependency': dependency}))
        for key, value in [('windows_recovery_release_revision', '0' * 40),
                           ('windows_recovery_release_repository', 'https://example.test/foreign.git')]:
            changed = dict(dependency, **{key: value})
            self.assertFalse(self.condition(guard['ansible.builtin.assert']['that'],
                                            {'windows_aap_network_dependency': changed}))

    def test_locked_clone_precedes_every_selected_reservation_and_boot(self):
        tasks = yaml.safe_load((ROOT / '01-win-vm-setup.yml').read_text())[0]['tasks']
        names = [row['name'] for row in tasks]
        clone = names.index('Create the selected Windows clone under the same lock as management NIC teardown')
        reserve = names.index("Reserve only the selected instance guest's exact resources after its locked disk creation")
        boot = names.index('Create and start Windows VM')
        self.assertLess(clone, reserve)
        self.assertLess(reserve, boot)
        old_clone = tasks[names.index('Create independent sparse qcow2 clone without resizing')]
        self.assertFalse(self.condition([old_clone['when']], {'windows_runtime_aap_management': {}}))
        ad = yaml.safe_load((ROOT / 'create_active_directory_vm.yml').read_text())
        self.assertEqual(ad[-1]['ansible.builtin.import_playbook'], '01-win-vm-setup.yml')

    def test_selected_fresh_ad_address_stage_defers_without_reservations_and_legacy_is_unchanged(self):
        play = yaml.safe_load((ROOT / 'configure_active_directory_address.yml').read_text())[0]
        end = next(row for row in play['pre_tasks'] if row.get('ansible.builtin.meta') == 'end_host')
        self.assertTrue(self.condition(end['when'], {'windows_runtime_settings_vault': 'ciphertext',
                                                     'ad_address_reservation_before_create': True}))
        self.assertFalse(self.condition(end['when'], {'ad_address_reservation_before_create': True}))
        self.assertFalse(self.condition(end['when'], {'windows_runtime_settings_vault': 'ciphertext',
                                                      'ad_address_reservation_before_create': False}))
        for task in play['tasks']:
            if task['name'] in ['Publish the exact LDAPS DNS name on the management network',
                                 "Add only the dedicated guest's persistent and live reservation"]:
                self.assertFalse(self.condition(task['when'], {'windows_runtime_settings_vault': 'ciphertext',
                     'ad_reservation_inspection': {'stdout': '{"dns_exists":false,"exists":false}'}}))


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Native Ansible is required.')
class NativeAnsibleCredentialBindingTests(unittest.TestCase):
    def test_invalid_legacy_clone_name_fails_before_os_or_network_preparation(self):
        play = yaml.safe_load((ROOT / '01-win-vm-setup.yml').read_text())[0]
        with tempfile.TemporaryDirectory(prefix='windows-invalid-clone-') as temporary:
            directory = Path(temporary)
            marker = directory / 'management-preparation-was-entered'
            # Keep the production task order/guards; instrument only the management entrypoint.
            management = next(row for row in play['tasks'] if row.get('ansible.builtin.include_tasks')
                              == 'tasks/windows_aap_management_network.yml')
            del management['ansible.builtin.include_tasks']
            management['ansible.builtin.file'] = {'path': str(marker), 'state': 'touch', 'mode': '0600'}
            play['become'] = False
            play['pre_tasks'] = []  # Loader identity/authentication has its separate native tests.
            play['vars_files'] = [str(ROOT / 'vars/main.yml')]
            play['vars'].update({'windows_runtime_settings_vault': 'synthetic-defined-ciphertext',
                'windows_runtime_aap_management': {}, 'vm_name': 'example-old', 'vm_role': 'managed',
                'windows_version': '2022', 'vm_network': 'example-isolated', 'vm_mac': '52:54:00:00:00:30',
                'windows_runtime_guests': {'example-owned': {'role': 'managed', 'version': '2022',
                    'interfaces': [{'network': 'example-isolated', 'mac': '52:54:00:00:00:30'}]}}})
            inventory = {'all': {'children': {'hypervisor': {'hosts': {'example-hypervisor': {
                         'ansible_connection': 'local', 'ansible_python_interpreter': sys.executable}}}}}}
            (directory / 'play.yml').write_text(yaml.safe_dump([play], sort_keys=False))
            (directory / 'inventory.yml').write_text(yaml.safe_dump(inventory))
            environment = dict(os.environ, ANSIBLE_HOME=str(directory / 'home'),
                               ANSIBLE_LOCAL_TEMP=str(directory / 'local'), ANSIBLE_REMOTE_TEMP=str(directory / 'remote'),
                               ANSIBLE_FILTER_PLUGINS=str(ROOT / 'filter_plugins'), ANSIBLE_NOCOLOR='1')
            result = subprocess.run(['ansible-playbook', '-i', str(directory / 'inventory.yml'),
                                     str(directory / 'play.yml')], cwd=ROOT, env=environment,
                                    text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            failed = result.stdout.split('fatal:', 1)[0].rsplit('TASK [', 1)[-1]
            self.assertIn("Require the selected instance's exact owned clone and interfaces", failed)
            self.assertFalse(marker.exists(), 'An invalid legacy VM request entered OS/network preparation.')

    def test_existing_os_injection_overrides_machine_login_only_for_the_selected_guest(self):
        outer = yaml.safe_load((ROOT / 'tasks/windows_aap_management_network.yml').read_text())[0]
        transaction = next(row for row in outer['block'] if row.get('rescue'))
        prelude = [row for row in outer['block'] if not row.get('rescue')]
        tasks = copy.deepcopy(prelude + transaction['block'][:2])
        with tempfile.TemporaryDirectory(prefix='windows-aap-binding-') as temporary:
            directory = Path(temporary)
            data = profile()
            variables = {'windows_runtime_settings_vault': 'synthetic-defined-ciphertext',
                         'windows_runtime_expected_instance': 'example-aap',
                         'windows_runtime_hypervisor': {'inventory_host': 'example-hypervisor'},
                         'windows_runtime_recovery_pin': data['route']['hypervisor'],
                         'windows_runtime_guests': {}, 'windows_runtime_aap_management': data,
                         'active_directory': {'test_vm_name': data['route']['vm_name'],
                                              'test_vm_uuid': data['primary']['uuid'],
                                              'test_ssh_address': data['primary']['address'],
                                              'test_aap_url': data['route']['aap_hostname']},
                         'windows_aap_management_state': 'present'}
            tasks.append({'name': 'Verify actual native add_host connection precedence',
                          'ansible.builtin.assert': {'that': [
                              "hostvars['windows_aap_management_target'].ansible_user == 'fixture-os-user'",
                              "hostvars['windows_aap_management_target'].ansible_password == 'fixture-os-password'",
                              "hostvars['windows_aap_management_target'].ansible_host == windows_runtime_aap_management.primary.address",
                              "hostvars['windows_aap_management_target'].ansible_port == 22",
                              "'StrictHostKeyChecking=yes' in hostvars['windows_aap_management_target'].ansible_ssh_common_args",
                              "'PubkeyAuthentication=no' in hostvars['windows_aap_management_target'].ansible_ssh_common_args"]}})
            cleanup = transaction['always']
            play = [{'hosts': 'example-hypervisor', 'gather_facts': False, 'vars': variables,
                     'tasks': [{'block': tasks, 'always': cleanup, 'no_log': True}]}]
            inventory = {'all': {'hosts': {'example-hypervisor': {'ansible_connection': 'local',
                         'ansible_python_interpreter': sys.executable}}}}
            (directory / 'play.yml').write_text(yaml.safe_dump(play))
            (directory / 'inventory.yml').write_text(yaml.safe_dump(inventory))
            environment = dict(os.environ, ANSIBLE_HOME=str(directory / 'home'),
                               ANSIBLE_LOCAL_TEMP=str(directory / 'local'),
                               ANSIBLE_REMOTE_TEMP=str(directory / 'remote'),
                               ANSIBLE_FILTER_PLUGINS=str(ROOT / 'filter_plugins'),
                               AD_AAP_TARGET_SSH_USERNAME='fixture-os-user',
                               AD_AAP_TARGET_SSH_PASSWORD='fixture-os-password',
                               AD_AAP_TARGET_SSH_KNOWN_HOSTS=data['primary']['address'] + ' ssh-ed25519 example\n')
            result = subprocess.run(['ansible-playbook', '-u', 'fixture-hypervisor-user',
                                     '-i', str(directory / 'inventory.yml'), str(directory / 'play.yml')],
                                    cwd=ROOT, env=environment, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
