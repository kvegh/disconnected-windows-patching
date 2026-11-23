"""Reject guessed Windows identities before invoking the shared release transaction."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import io
import json

from ansible.errors import AnsibleFilterError
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.template import Templar
import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('windows_guest_provenance', ROOT / 'filter_plugins/windows_guest_provenance.py')
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)
NATIVE_SPEC = importlib.util.spec_from_file_location('windows_guest_native', ROOT / 'assets/windows-guest-native-proof.py')
native_probe = importlib.util.module_from_spec(NATIVE_SPEC)
NATIVE_SPEC.loader.exec_module(native_probe)


def fixture(count=2):
    name, instance = 'example-v07', 'aap27-test-7'
    uuid = '11111111-2222-3333-4444-555555555555'
    nics = [{'network': 'isolated', 'mac': '52:54:00:00:00:01',
             'address': '192.168.70.10', 'dns_name': name}]
    if count == 2:
        nics.append({'network': 'management', 'mac': '52:54:00:00:00:02',
                     'address': '192.168.71.10', 'dns_name': name + '-mgmt'})
    guest = {'role': 'wsus', 'version': '2025', 'interfaces': nics}
    pin = {'machine_id': 'a' * 32}
    computer = {'computer_name': name.upper(), 'computer_uuid': uuid.upper(),
                'part_of_domain': False, 'domain': 'WORKGROUP', 'os_product_type': 3, 'os_build': '26100',
                'interfaces': [{'mac': nic['mac'].upper().replace(':', '-'), 'addresses': [nic['address']]} for nic in nics],
                'update_urls': []}
    interfaces = ''.join('<interface type="network"><source network="%s"/><mac address="%s"/></interface>'
                         % (nic['network'], nic['mac']) for nic in nics)
    disk = '/opt/vms/win-' + name + '-clone.disk.qcow2'
    xml = ('<domain><name>%s</name><uuid>%s</uuid><description>aap-disconnected-windows-clone</description>'
           '<title>%s:%s</title><devices><disk device="disk"><source file="%s"/></disk>%s</devices></domain>') % (
               name, uuid, instance, name, disk, interfaces)
    networks = {}
    for index, nic in enumerate(nics):
        definition = '<network><name>%s</name><bridge name="vmbr%s"/></network>' % (nic['network'], index)
        networks[nic['network']] = {'persistent': definition, 'current': definition}
    native = {'hypervisor_machine_id': pin['machine_id'], 'persistent_xml': xml, 'current_xml': xml,
              'networks': networks, 'snapshots': [],
              'disk': {'path': disk, 'regular': True, 'symlink': False, 'links': 1, 'standalone_qcow2': True}}
    trust = {'scheme': 'https', 'validation': 'validate', 'ca_present': True}
    return [computer, native, instance, name, guest, nics[-1]['address'], pin, trust,
            {'dns_domain': 'ad.v07.example.test'}, {name: guest}]


class WindowsGuestProvenanceTests(unittest.TestCase):
    def test_checked_failure_reason_preserves_proof_rules_without_exposing_private_evidence(self):
        values = fixture()
        self.assertTrue(proof.checked_provenance(*values)['verified'])
        values[0]['update_urls'] = ['https://example.invalid/synthetic-private-value']
        checked = proof.checked_provenance(*values)
        self.assertFalse(checked['verified'])
        self.assertEqual(checked['reason'], 'An inherited update-service endpoint prevents guest release.')
        self.assertNotIn('synthetic-private-value', json.dumps(checked))
        with patch.object(proof, 'provenance', side_effect=RuntimeError('synthetic-private-value')):
            checked = proof.checked_provenance(*fixture())
        self.assertEqual(checked, {'verified': False, 'reason': 'Protected Windows provenance verification failed.'})
        task = next(row for row in yaml.safe_load((ROOT / 'tasks/windows_verified_guest_release.yml').read_text())[3]['block']
                    if row['name'].startswith('Require actual Windows'))
        rendered = Templar(loader=DataLoader(), variables={'windows_runtime_provenance_check': dict(
            checked, invocation={'password': 'synthetic-private-value'}, stderr='synthetic-private-value')}).template(
                task['ansible.builtin.assert']['fail_msg'])
        self.assertEqual(rendered, checked['reason'])
        self.assertNotIn('synthetic-private-value', rendered)

    def test_real_one_and_two_nic_windows_identity_produces_only_shared_windows_fields(self):
        for count in [1, 2]:
            values = fixture(count)
            original = deepcopy(values)
            result = proof.provenance(*values)
            self.assertEqual(result['kind'], 'windows')
            self.assertTrue(result['verified'])
            self.assertTrue(result['winrm_certificate_validated'])
            self.assertEqual(result['computer_uuid'], '11111111-2222-3333-4444-555555555555')
            self.assertEqual(result['address'], values[5])
            self.assertEqual(len(result['interfaces']), count)
            self.assertNotIn('machine_id', result)
            self.assertNotIn('host_keys', result)
            self.assertEqual(values, original)

    def test_real_winrm_trust_and_versioned_computer_identity_are_mandatory(self):
        for variant in ['http', 'unknown-policy', 'no-ca', 'foreign-name', 'unicode-name', 'foreign-uuid', 'client-os', 'wrong-build']:
            values = fixture()
            computer, trust = values[0], values[7]
            if variant == 'http': trust['scheme'] = 'http'
            elif variant == 'unknown-policy': trust['validation'] = 'disabled'
            elif variant == 'no-ca': trust['ca_present'] = False
            elif variant == 'foreign-name': computer['computer_name'] = 'foreign-v07'
            elif variant == 'unicode-name': computer['computer_name'] = '\u212aXAMPLE-V07'
            elif variant == 'foreign-uuid': computer['computer_uuid'] = '99999999-2222-3333-4444-555555555555'
            elif variant == 'client-os': computer['os_product_type'] = 1
            elif variant == 'wrong-build': computer['os_build'] = '20348'
            with self.subTest(variant=variant), self.assertRaises(AnsibleFilterError):
                proof.provenance(*values)

    def test_approved_lab_policy_records_false_without_weakening_native_identity(self):
        values = fixture()
        values[7] = {'scheme': 'https', 'validation': 'ignore', 'ca_present': False}
        result = proof.provenance(*values)
        self.assertTrue(result['verified'])
        self.assertIs(result['winrm_certificate_validated'], False)
        values[0]['computer_uuid'] = '99999999-2222-3333-4444-555555555555'
        with self.assertRaises(AnsibleFilterError):
            proof.provenance(*values)

    def test_observed_mac_ip_and_primary_management_nic_cannot_be_copied_or_guessed(self):
        for variant in ['foreign-mac', 'foreign-ip', 'extra-ip', 'missing-nic', 'extra-nic', 'primary']:
            values = fixture()
            if variant == 'foreign-mac': values[0]['interfaces'][0]['mac'] = '52:54:00:99:99:99'
            elif variant == 'foreign-ip': values[0]['interfaces'][0]['addresses'] = ['192.168.70.99']
            elif variant == 'extra-ip': values[0]['interfaces'][0]['addresses'].append('192.168.70.99')
            elif variant == 'missing-nic': values[0]['interfaces'].pop()
            elif variant == 'extra-nic': values[0]['interfaces'].append({'mac': '52:54:00:99:99:99', 'addresses': []})
            elif variant == 'primary': values[5] = '192.168.70.99'
            with self.subTest(variant=variant), self.assertRaises(AnsibleFilterError):
                proof.provenance(*values)

    def test_inherited_forest_and_update_service_are_refused(self):
        for variant in ['forest', 'url', 'embedded-login']:
            values = fixture()
            if variant == 'forest': values[0].update(part_of_domain=True, domain='original.example.test')
            elif variant == 'url': values[0]['update_urls'] = ['http://original.example.test:8530']
            elif variant == 'embedded-login': values[0]['update_urls'] = ['http://user:password@example-v07:8530']
            with self.subTest(variant=variant), self.assertRaises(AnsibleFilterError):
                proof.provenance(*values)
        values = fixture()
        values[0].update(part_of_domain=True, domain=values[8]['dns_domain'].upper())
        values[0]['update_urls'] = ['http://example-v07:8530']
        self.assertTrue(proof.provenance(*values)['verified'])

    def test_every_native_owner_disk_nic_bridge_and_machine_proof_is_required(self):
        for variant in ['machine', 'marker', 'title', 'disk', 'snapshot', 'link', 'backing', 'native-nic', 'current-uuid', 'bridge']:
            values = fixture()
            native = values[1]
            if variant == 'machine': native['hypervisor_machine_id'] = 'b' * 32
            elif variant == 'marker': native['persistent_xml'] = native['persistent_xml'].replace('aap-disconnected-windows-clone', 'foreign')
            elif variant == 'title': native['persistent_xml'] = native['persistent_xml'].replace(values[2] + ':', 'foreign:')
            elif variant == 'disk': native['disk']['path'] = '/opt/images/golden.qcow2'
            elif variant == 'snapshot': native['snapshots'] = ['some-snapshot']
            elif variant == 'link': native['disk']['links'] = 2
            elif variant == 'backing': native['disk']['standalone_qcow2'] = False
            elif variant == 'native-nic': native['current_xml'] = native['current_xml'].replace('52:54:00:00:00:02', '52:54:00:99:99:99')
            elif variant == 'current-uuid': native['current_xml'] = native['current_xml'].replace('11111111-', '99999999-')
            elif variant == 'bridge': native['networks']['management']['current'] = native['networks']['management']['current'].replace('vmbr1', 'foreign')
            with self.subTest(variant=variant), self.assertRaises(AnsibleFilterError):
                proof.provenance(*values)


class WindowsProducerGuardsTests(unittest.TestCase):
    def evaluate(self, expressions, values):
        loader = DataLoader()
        conditional = Conditional(loader=loader)
        conditional.when = expressions
        return conditional.evaluate_conditional(Templar(loader=loader, variables=values), values)

    def test_shared_role_requires_exact_reviewed_dependency_before_checkout(self):
        role = ROOT / 'roles/windows_recovery_release'
        defaults = yaml.safe_load((role / 'defaults/main.yml').read_text())
        guard = yaml.safe_load((role / 'tasks/main.yml').read_text())[0]
        values = dict(defaults, aap_hactar_source_revision='a' * 40,
            hactar_source_public_ip='198.51.100.10', windows_runtime_verified_resource={
            'kind': 'windows', 'verified': True, 'winrm_certificate_validated': True,
            'vm_name': 'example-v07', 'instance_name': 'aap27-test-7', 'hypervisor_machine_id': 'a' * 32},
            inventory_hostname='example-v07', windows_runtime_expected_instance='aap27-test-7',
            ansible_winrm_server_cert_validation='validate',
            windows_runtime_recovery_pin={'machine_id': 'a' * 32},
            windows_runtime_release_trust={'path': '/tmp/windows-release-known-hosts-fixture'})
        expressions = guard['ansible.builtin.assert']['that']
        self.assertTrue(self.evaluate(expressions, values))
        for revision in ['feab264664caa4cd8e3554aaf0a7d825f2fbb384',
                         'bdda318620ae30ebea455376442dc509ec7fb583',
                         'b1587dc7e76df7320815fc8199be1a98144e2fe5',
                         '90edda0546fe149d317846d8d257fefe7abf6319',
                         'e0a96b1c13c756faf7cef3ca7ca3fe2dcc3b1e2e',
                         '3f5c7e253133d9b25e7a213cdb45bebdabca3f17',
                         'ae9cfdbdbf29fe0471b71a0163cd557f607d7d8c',
                         '6de45e0a10a4119d596e1ed65c22c6ee48360e4a', '0' * 40, 'main']:
            with self.subTest(revision=revision):
                self.assertFalse(self.evaluate(expressions, dict(values, windows_recovery_release_revision=revision)))
        self.assertFalse(self.evaluate(expressions, dict(values, windows_recovery_release_repository='https://example.invalid/other.git')))
        for key in ['aap_hactar_source_revision', 'hactar_source_public_ip']:
            missing = dict(values)
            del missing[key]
            self.assertFalse(self.evaluate(expressions, missing))

    def test_retirement_requires_the_same_current_pin_before_checkout(self):
        defaults = yaml.safe_load((ROOT / 'roles/windows_recovery_release/defaults/main.yml').read_text())
        tasks = yaml.safe_load((ROOT / 'tasks/windows_retire_guest.yml').read_text())
        guard = next(row for row in tasks if row['name'].startswith('Require the same reviewed public implementation'))
        expressions = guard['ansible.builtin.assert']['that']
        self.assertTrue(self.evaluate(expressions, {'windows_retire_dependency': defaults}))
        for revision in ['feab264664caa4cd8e3554aaf0a7d825f2fbb384',
                         'bdda318620ae30ebea455376442dc509ec7fb583',
                         'b1587dc7e76df7320815fc8199be1a98144e2fe5', '0' * 40, 'main']:
            with self.subTest(revision=revision):
                changed = dict(defaults, windows_recovery_release_revision=revision)
                self.assertFalse(self.evaluate(expressions, {'windows_retire_dependency': changed}))
        changed = dict(defaults, windows_recovery_release_repository='https://example.invalid/foreign.git')
        self.assertFalse(self.evaluate(expressions, {'windows_retire_dependency': changed}))

    def test_existing_bootstrap_login_is_bound_only_to_initial_standalone_guest_configuration(self):
        tasks = yaml.safe_load((ROOT / 'tasks/windows_runtime_settings.yml').read_text())
        task = next(row for row in tasks if row['name'].startswith('Bind the existing private Windows bootstrap login'))
        values = {'windows_runtime_bind_bootstrap_login': True, 'inventory_hostname': 'example-v07',
                  'windows_runtime_guests': {'example-v07': {'role': 'managed'}},
                  'groups': {'windows_managed': ['example-v07']}}
        self.assertTrue(self.evaluate(task['when'], values))
        for variant in ['localhost', 'hypervisor', 'ad', 'other-play', 'outside-group']:
            changed = deepcopy(values)
            if variant in ['localhost', 'hypervisor']: changed['inventory_hostname'] = variant
            elif variant == 'ad': changed['windows_runtime_guests']['example-v07']['role'] = 'ad'
            elif variant == 'other-play': changed['windows_runtime_bind_bootstrap_login'] = False
            elif variant == 'outside-group': changed['groups'] = {}
            with self.subTest(variant=variant):
                self.assertFalse(self.evaluate(task['when'], changed))
        self.assertTrue(task['no_log'])

    def test_release_requires_full_unskipped_normal_run_and_real_trust(self):
        first = yaml.safe_load((ROOT / 'tasks/windows_verified_guest_release.yml').read_text())[0]
        values = {'ansible_run_tags': ['all'], 'ansible_skip_tags': [], 'ansible_check_mode': False,
                  'windows_runtime_recovery_pin': {'address': '192.0.2.1', 'port': 22, 'machine_id': 'a' * 32},
                  'windows_runtime_hypervisor': {'address': '192.0.2.1', 'port': 22, 'machine_id': 'a' * 32},
                  'inventory_hostname': 'example-v07', 'windows_runtime_guests': {'example-v07': {}},
                  'windows_hostname': 'example-v07', 'active_directory': {'hostname': 'ad-v07'},
                  'ansible_connection': 'winrm', 'ansible_winrm_scheme': 'https',
                  'ansible_port': 5986, 'ansible_winrm_transport': 'ntlm',
                  'ansible_winrm_server_cert_validation': 'validate', 'windows_runtime_ca_file': {'path': '/tmp/fixture-ca'}}
        expressions = first['ansible.builtin.assert']['that']
        self.assertTrue(self.evaluate(expressions, values))
        self.assertTrue(self.evaluate(expressions, dict(values, ansible_run_tags=('all',))))
        for field, value in [('ansible_run_tags', ['all', 'partial']),
                             ('ansible_run_tags', ['all', 'all']),
                             ('ansible_run_tags', []), ('ansible_run_tags', 'all'),
                             ('ansible_run_tags', ['partial']), ('ansible_skip_tags', ['some-task']),
                             ('ansible_check_mode', True), ('ansible_port', 5985),
                             ('ansible_winrm_server_cert_validation', 'disabled'), ('ansible_winrm_scheme', 'http'),
                             ('ansible_connection', 'local'), ('windows_runtime_ca_file', {})]:
            with self.subTest(field=field):
                self.assertFalse(self.evaluate(expressions, dict(values, **{field: value})))
        self.assertTrue(self.evaluate(expressions, dict(values,
            ansible_winrm_server_cert_validation='ignore', windows_runtime_ca_file={})))

    def test_native_probe_refuses_wrong_machine_before_any_libvirt_or_disk_command(self):
        request = {'name': 'example-v07', 'hypervisor_machine_id': 'a' * 32}
        with patch.object(native_probe.sys, 'stdin', io.StringIO(json.dumps(request))), \
             patch.object(native_probe.Path, 'read_text', return_value='b' * 32), \
             patch.object(native_probe.subprocess, 'check_output') as command:
            with self.assertRaises(ValueError):
                native_probe.main()
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
