"""Exercise selected-instance and exact network-resource safety offline."""

import copy
import base64
import importlib.util
from pathlib import Path
import unittest

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


class WindowsLDAPCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = {'prefix': 'example', 'fqdn': 'example-ad.example.test',
                          'groups': [{'scope': 'DomainLocal', 'region': 'DK', 'role': 'reader'}]}
        self.local = {'id': 1, 'name': 'Built-in password authentication', 'configuration': {},
                      'type': 'ansible_base.authentication.authenticator_plugins.local'}
        self.owned = {'id': 2, 'name': 'example Active Directory',
                      'type': 'ansible_base.authentication.authenticator_plugins.ldap',
                      'configuration': {'SERVER_URI': ['ldaps://example-ad.example.test:636']}}
        self.maps = [{'id': 10, 'name': 'Shared local mapping', 'authenticator': 1},
                     {'id': 20, 'name': 'Regional demo login', 'authenticator': 2}]

    def test_only_exact_test_authentication_is_selected_and_builtin_is_preserved(self):
        plan = runtime.ldap_cleanup([self.local, self.owned], self.maps, self.directory)
        self.assertEqual(plan['authenticator']['id'], 2)
        self.assertEqual(plan['map_names'], ['Regional demo login'])
        self.assertEqual(plan['preserved_authenticator_ids'], [1])
        self.assertEqual(plan['preserved_map_ids'], [10])

    def test_absent_test_authentication_preserves_every_existing_object(self):
        plan = runtime.ldap_cleanup([self.local], self.maps[:1], self.directory)
        self.assertIsNone(plan['authenticator'])
        self.assertEqual(plan['preserved_authenticator_ids'], [1])
        self.assertEqual(plan['preserved_map_ids'], [10])

    def test_shared_endpoint_or_foreign_name_is_rejected(self):
        for key, value in [('name', 'Another LDAP'), ('configuration', {'SERVER_URI': ['ldaps://another.example.test:636']})]:
            changed = copy.deepcopy(self.owned)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(AnsibleFilterError):
                runtime.ldap_cleanup([self.local, changed], self.maps, self.directory)
        with self.assertRaises(AnsibleFilterError):
            runtime.ldap_cleanup([self.local, self.owned, dict(self.owned, id=3)], self.maps, self.directory)

    def test_unreviewed_map_on_the_test_authenticator_is_rejected(self):
        with self.assertRaises(AnsibleFilterError):
            runtime.ldap_cleanup([self.local, self.owned], self.maps +
                                 [{'id': 21, 'name': 'Unexpected external mapping', 'authenticator': 2}], self.directory)


class WindowsCleanupConditionTests(unittest.TestCase):
    def evaluate(self, file, task_name, variables):
        block = yaml.safe_load((ROOT / 'tasks' / file).read_text())[0]['block']
        task = next(row for row in block if row['name'] == task_name)
        values = dict(task.get('vars', {}), **variables)
        loader = DataLoader()
        condition = Conditional(loader=loader)
        condition.when = task['ansible.builtin.assert']['that']
        return condition.evaluate_conditional(Templar(loader=loader, variables=values), values)

    def test_ldap_preview_requires_a_boolean_mode_and_exact_selected_ownership(self):
        names = list(profile()['windows_runtime']['settings']['windows_runtime_guests'])
        values = {'windows_runtime_settings_vault': 'example ciphertext',
                  'windows_decommission_apply': True, 'windows_runtime_expected_instance': 'example-instance',
                  'windows_demo_vm_names': names,
                  'windows_decommission_preview': {'read_only': True, 'instance': 'example-instance',
                                                   'domains': dict.fromkeys(names, {})},
                  'ad_target_api_url': 'https://example-aap.example.test',
                  'active_directory': {'test_aap_url': 'https://example-aap.example.test'}}
        task = 'Require an explicit cleanup mode and the reviewed five-guest ownership preview'
        self.assertTrue(self.evaluate('windows_remove_ldap.yml', task, values))
        self.assertTrue(self.evaluate('windows_remove_ldap.yml', task, dict(values, windows_decommission_apply=False)))
        for change in [
            {'windows_decommission_apply': 'yes'},
            {'ad_target_api_url': 'https://different-aap.example.test'},
            {'windows_decommission_preview': dict(values['windows_decommission_preview'], instance='another-instance')},
            {'windows_decommission_preview': dict(values['windows_decommission_preview'], domains={'unrelated': {}})},
        ]:
            with self.subTest(change=list(change)):
                self.assertFalse(self.evaluate('windows_remove_ldap.yml', task, dict(values, **change)))

    def test_ca_anchor_must_contain_exactly_the_selected_certificate(self):
        task = 'Refuse removal of an anchor belonging to another certificate'
        for content, expected in [('example public CA', True), ('another public CA', False)]:
            values = {'active_directory': {'ca_certificate': 'example public CA'},
                      'windows_ad_anchor_content': {'content': base64.b64encode(content.encode()).decode()}}
            self.assertEqual(self.evaluate('windows_remove_ad_ca.yml', task, values), expected)

    def test_shared_gateway_bundle_requires_the_exact_owned_block(self):
        begin = '# BEGIN ANSIBLE MANAGED example AD DEMO CA'
        end = '# END ANSIBLE MANAGED example AD DEMO CA'
        owned = begin + '\nexample public CA\n' + end
        for content, expected in [(owned, True), ('unrelated CA', True),
                                  (begin + '\nanother public CA\n' + end, False),
                                  ('example public CA', False), (begin, False)]:
            with self.subTest(content=content):
                values = {'active_directory': {'prefix': 'example', 'ca_certificate': 'example public CA'},
                          'windows_ad_gateway_bundle': {'content': base64.b64encode(content.encode()).decode()}}
                self.assertEqual(self.evaluate('windows_remove_ad_ca.yml',
                    'Require the exact owned block or a previously completed removal', values), expected)


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
