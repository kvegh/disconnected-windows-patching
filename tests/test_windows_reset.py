"""Check normal reset planning and important wrong-target refusals offline."""
import copy
import importlib.util
import json
from pathlib import Path
import ssl
import unittest
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

from test_active_directory_migration import fixture, FixtureAPI
from test_active_directory_verifier import FakeAAP
from test_windows_runtime import ownership
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('windows_ad_cleanup', ROOT / 'assets/windows-ad-cleanup.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class API(FixtureAPI):
    def listing(self, path):
        parts = urlsplit(path).path.strip('/').split('/')
        endpoint = parts[3]
        if endpoint in ('role_team_assignments', 'role_user_assignments', 'role_definitions'):
            return copy.deepcopy(self.data.get(endpoint, []))
        if len(parts) == 6 and endpoint == 'teams':
            return copy.deepcopy(self.data['users'])
        if len(parts) == 6 and endpoint == 'users':
            return copy.deepcopy(self.data.get('foreign_membership', []))
        return super().listing(path)


def ad_fixture():
    p = FakeAAP().profile
    p['verify_logins'] = False
    p['prefix'] = 'Example'
    for user in p['users']:
        user['username'] = user['username'].replace('demo-', 'example-')
    for user in p['retired_users']:
        user['username'] = user['username'].replace('demo-', 'example-')
    d = fixture(migrated=True, keep_old_project=False)
    d['users'] = [dict(id=500 + i, username=user['username'], is_superuser=False,
                       is_platform_auditor=False, associated_authenticators={'7': {}})
                  for i, user in enumerate(p['users'])]
    d['role_definitions'] = [dict(id=700 + i, name='Example ' + kind + ' Reader',
                                  content_type='awx.' + kind, permissions=['awx.view_' + kind])
                             for i, kind in enumerate(cleanup.verification.ENDPOINTS)]
    return p, d


class WindowsResetTests(unittest.TestCase):
    def test_transport_failure_categories_do_not_expose_private_error_details(self):
        secret = 'synthetic-private-password'
        error = URLError(ssl.SSLCertVerificationError(1, secret))
        self.assertEqual(cleanup.failure_reason(error), 'The selected AAP API certificate failed validation.')
        self.assertNotIn(secret, cleanup.failure_reason(RuntimeError(secret)))
        self.assertEqual(cleanup.failure_reason(AssertionError('An inspection API read failed: HTTP 401')),
                         'An inspection API read failed: HTTP 401')

    def test_baseline_failure_message_uses_only_the_protected_readers_safe_reason(self):
        tasks = yaml.safe_load((ROOT / 'capture_windows_teardown_baseline.yml').read_text())[0]['tasks']
        reader = next(row for row in tasks if row.get('register') == 'windows_ad_ownership')
        self.assertTrue(reader['no_log'])
        self.assertFalse(reader['failed_when'])
        check = next(row for row in tasks if row['name'].endswith('with a safe failure reason'))
        reason = 'The selected AAP API certificate failed validation.'
        values = {'windows_ad_ownership': {'rc': 1, 'stdout': json.dumps({'reason': reason}),
                                          'stderr': 'synthetic-private-password',
                                          'invocation': {'stdin': 'synthetic-private-password'}}}
        rendered = Templar(loader=DataLoader(), variables=values).template(check['ansible.builtin.assert']['fail_msg'])
        self.assertEqual(rendered, reason)
        self.assertNotIn('synthetic-private-password', rendered)

    def test_normal_dedicated_ad_plan_and_absent_retry(self):
        p, d = ad_fixture()
        saved = cleanup.snapshot(p, API(d))
        self.assertEqual([len(saved[k]) for k in ('job_templates', 'projects', 'users', 'role_definitions')],
                         [10, 5, 12, 4])
        empty = {key: [] for key in saved if key != 'prefix'}
        empty['prefix'] = p['prefix']
        d['authenticators'] = []
        current = cleanup.snapshot(dict(p, saved=saved), API(d))
        self.assertEqual(cleanup.remaining(current, saved, empty), saved)
        for key in ('organizations', 'job_templates', 'projects', 'inventories', 'credentials',
                    'teams', 'users', 'role_definitions'):
            d[key] = []
        current = cleanup.snapshot(dict(p, saved=saved), API(d))
        self.assertEqual(cleanup.remaining(current, saved, empty), empty)

    def test_ldap_must_be_removed_before_regional_objects(self):
        p, d = ad_fixture()
        with self.assertRaisesRegex(AssertionError, 'LDAP'):
            cleanup.snapshot(dict(p, saved={}), API(d))

    def test_changed_or_shared_demo_objects_are_refused(self):
        for fault in ('source', 'playbook', 'superuser', 'foreign-grant', 'foreign-membership'):
            p, d = ad_fixture()
            if fault == 'source': d['projects'][0]['scm_url'] = 'https://foreign.example.test/repo.git'
            if fault == 'playbook': d['job_templates'][0]['playbook'] = 'foreign.yml'
            if fault == 'superuser': d['users'][0]['is_superuser'] = True
            if fault == 'foreign-grant':
                d['role_team_assignments'] = [{'role_definition': 700, 'object_id': 9999}]
            if fault == 'foreign-membership': d['foreign_membership'] = [{'id': 9999}]
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                cleanup.snapshot(p, API(d))

    def test_preexisting_or_replaced_resource_is_never_claimed_for_cleanup(self):
        p, d = ad_fixture(); saved = cleanup.snapshot(p, API(d))
        with self.assertRaisesRegex(AssertionError, 'predates'):
            cleanup.remaining(saved, saved, saved)
        before = {key: [] for key in saved if key != 'prefix'}; before['prefix'] = p['prefix']
        current = copy.deepcopy(saved); current['projects'][0]['id'] = 9999
        with self.assertRaises(AssertionError):
            cleanup.remaining(current, saved, before)

    def test_native_clone_and_complete_absence_use_real_original_uuid(self):
        name, instance = 'example-v01', 'example-aap'
        nic = {'network': 'example', 'mac': '52:54:00:00:00:01',
               'address': '192.0.2.10', 'dns_name': name}
        guests = {name: {'interfaces': [nic]}}
        xml = ('<domain><name>' + name + '</name><uuid>11111111-1111-4111-8111-111111111111</uuid>'
               '<description>aap-disconnected-windows-clone</description><title>' + instance + ':' + name + '</title>'
               '<devices><disk device="disk"><source file="/opt/vms/win-' + name + '-clone.disk.qcow2"/></disk>'
               '<interface><mac address="52:54:00:00:00:01"/><source network="example"/></interface></devices></domain>')
        saved = ownership.inspect(instance, guests, {name: xml})
        record = {'name': name, 'instance': instance, 'guests': guests,
                  'preview': {'instance': instance, 'read_only': True, 'domains': saved}}
        self.assertTrue(ownership.selected(record, {name: xml}, {name: xml}, True)['present'])
        self.assertFalse(ownership.selected(record, {}, {}, False)['present'])
        with self.assertRaises(ValueError): ownership.selected(record, {}, {}, True)
        with self.assertRaises(ValueError):
            ownership.selected(record, {name: xml.replace(instance + ':', 'foreign:')}, {}, True)

    def test_native_only_cleanup_refuses_any_matching_managed_permission(self):
        guest = {'interfaces': [{'address': '192.0.2.10', 'mac': '52:54:00:00:00:01'}]}
        ownership.unconfigured_permissions(guest, {})
        for field in ('https_clients', 'http_clients', 'released_clients', 'guest_host_clients'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                ownership.unconfigured_permissions(guest, {field: [{'ipv4': '192.0.2.10',
                    'mac': '52:54:00:00:00:01', 'bridge': 'example'}]})


if __name__ == '__main__':
    unittest.main()
