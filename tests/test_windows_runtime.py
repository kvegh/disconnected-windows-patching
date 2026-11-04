"""Exercise selected-instance and exact network-resource safety offline."""

import copy
import importlib.util
from pathlib import Path
import unittest

from ansible.errors import AnsibleFilterError


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('windows_runtime', ROOT / 'filter_plugins/windows_runtime.py')
network = load('windows_network', ROOT / 'assets/windows-network-reservations.py')
ownership = load('windows_ownership', ROOT / 'assets/windows-environment-ownership.py')


def profile():
    names = ['example-ext', 'example-int', 'example-win22', 'example-win25', 'example-ad']
    guests = {name: {'role': 'ad' if index == 5 else 'managed', 'version': '2025',
                     'interfaces': [{'network': 'example-network',
                                     'mac': '52:54:00:00:00:%02x' % index,
                                     'address': '192.0.2.%d' % (10 + index), 'dns_name': name}]}
              for index, name in enumerate(names, 1)}
    return {'windows_runtime': {'schema': 1, 'instance': 'example-instance', 'settings': {
        'windows_runtime_hypervisor': {'inventory_host': 'example-hypervisor', 'address': '192.0.2.1',
                                      'port': 22, 'machine_id': '0' * 32,
                                      'known_hosts': '192.0.2.1 ssh-ed25519 example-key\n'},
        'windows_runtime_guests': guests, 'windows_demo_vm_names': names,
        'windows_demo_include_ad': True, 'windows_runtime_winrm_ready': False,
        'active_directory': {'hostname': 'example-ad', 'dns_domain': 'example.test',
                             'fqdn': 'example-ad.example.test'},
    }}}


class WindowsRuntimeTests(unittest.TestCase):
    def test_approved_profile_is_bound_to_one_exact_instance(self):
        document = profile()
        self.assertEqual(runtime.selected_settings(document, 'example-instance'),
                         document['windows_runtime']['settings'])
        with self.assertRaises(AnsibleFilterError):
            runtime.selected_settings(document, 'different-instance')

    def test_unreviewed_ansible_connection_override_is_rejected(self):
        document = profile()
        document['windows_runtime']['settings']['ansible_ssh_common_args'] = 'unsafe override'
        with self.assertRaises(AnsibleFilterError):
            runtime.selected_settings(document, 'example-instance')

    def test_duplicate_mac_or_address_is_rejected(self):
        for key in ('mac', 'address'):
            with self.subTest(key=key):
                document = profile()
                guests = document['windows_runtime']['settings']['windows_runtime_guests']
                guests['example-int']['interfaces'][0][key] = guests['example-ext']['interfaces'][0][key]
                with self.assertRaises(AnsibleFilterError):
                    runtime.selected_settings(document, 'example-instance')

    def test_windows_name_limit_and_missing_machine_pin_are_rejected(self):
        document = profile()
        values = document['windows_runtime']['settings']
        values['windows_runtime_hypervisor']['machine_id'] = ''
        with self.assertRaises(AnsibleFilterError):
            runtime.selected_settings(document, 'example-instance')
        document = profile()
        values = document['windows_runtime']['settings']
        old = 'example-ext'
        long_name = 'example-name-too-long'
        values['windows_runtime_guests'][long_name] = values['windows_runtime_guests'].pop(old)
        values['windows_demo_vm_names'][0] = long_name
        with self.assertRaises(AnsibleFilterError):
            runtime.selected_settings(document, 'example-instance')

    def test_winrm_readiness_requires_its_public_issuer(self):
        document = profile()
        document['windows_runtime']['settings']['windows_runtime_winrm_ready'] = True
        with self.assertRaises(AnsibleFilterError):
            runtime.selected_settings(document, 'example-instance')


class WindowsReservationTests(unittest.TestCase):
    def setUp(self):
        self.nic = {'network': 'example-network', 'mac': '52:54:00:00:00:01',
                    'address': '192.0.2.11', 'dns_name': 'example-ext'}
        self.xml = '<network><name>example-network</name><dns>{dns}</dns><ip address="192.0.2.1" prefix="24"><dhcp>{dhcp}</dhcp></ip></network>'

    def test_absent_exact_resources_can_be_planned_without_widening(self):
        plan = network.inspect(self.nic, self.xml.format(dns='', dhcp=''), [])
        self.assertFalse(plan['dhcp_exists'])
        self.assertFalse(plan['dns_exists'])
        self.assertIn('name="example-ext"', plan['dhcp_xml'])

    def test_exact_existing_records_are_idempotent(self):
        dhcp = '<host mac="52:54:00:00:00:01" ip="192.0.2.11" name="example-ext"/>'
        dns = '<host ip="192.0.2.11"><hostname>example-ext</hostname></host>'
        plan = network.inspect(self.nic, self.xml.format(dns=dns, dhcp=dhcp), [])
        self.assertTrue(plan['dhcp_exists'])
        self.assertTrue(plan['dns_exists'])

    def test_conflicting_or_shared_dns_and_dhcp_are_rejected(self):
        cases = [
            ('', '<host mac="52:54:00:00:00:02" ip="192.0.2.11" name="another-guest"/>'),
            ('<host ip="192.0.2.11"><hostname>example-ext</hostname><hostname>shared-name</hostname></host>', ''),
            ('<host ip="192.0.2.12"><hostname>example-ext</hostname></host>', ''),
        ]
        for dns, dhcp in cases:
            with self.subTest(dns=dns, dhcp=dhcp), self.assertRaises(ValueError):
                network.inspect(self.nic, self.xml.format(dns=dns, dhcp=dhcp), [])

    def test_other_nic_lease_is_rejected(self):
        with self.assertRaises(ValueError):
            network.inspect(self.nic, self.xml.format(dns='', dhcp=''),
                            [{'mac': '52:54:00:00:00:02', 'ipaddr': '192.0.2.11'}])


class WindowsOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.guests = {'example-guest': {'interfaces': [{'network': 'example-network',
                         'mac': '52:54:00:00:00:01', 'address': '192.0.2.11', 'dns_name': 'example-guest'}]}}
        self.xml = ('<domain><name>example-guest</name><uuid>11111111-1111-1111-1111-111111111111</uuid>'
                    '<description>aap-disconnected-windows-clone</description>'
                    '<title>example-instance:example-guest</title><devices><disk device="disk">'
                    '<source file="/opt/vms/win-example-guest-clone.disk.qcow2"/></disk>'
                    '<interface type="network"><mac address="52:54:00:00:00:01"/>'
                    '<source network="example-network"/></interface></devices></domain>')

    def test_exact_namespaced_clone_is_previewed_without_changing_it(self):
        result = ownership.inspect('example-instance', self.guests, {'example-guest': self.xml})
        self.assertEqual(result['example-guest']['uuid'], '11111111-1111-1111-1111-111111111111')

    def test_wrong_owner_disk_or_network_is_rejected(self):
        for old, new in [('example-instance:', 'another-instance:'),
                         ('win-example-guest-clone.disk.qcow2', 'shared-golden.qcow2'),
                         ('network="example-network"', 'network="other-network"')]:
            with self.subTest(field=old), self.assertRaises(ValueError):
                ownership.inspect('example-instance', self.guests, {'example-guest': self.xml.replace(old, new)})

    def test_missing_guest_or_shared_disk_is_rejected(self):
        with self.assertRaises(ValueError):
            ownership.inspect('example-instance', self.guests, {})
        with self.assertRaises(ValueError):
            ownership.inspect('example-instance', self.guests, {'example-guest': self.xml, 'unrelated': self.xml})


if __name__ == '__main__':
    unittest.main()
