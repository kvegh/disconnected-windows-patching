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
            rows = self.data.get(endpoint, [])
            if endpoint == 'role_user_assignments':
                for key, values in parse_qs(urlsplit(path).query).items():
                    rows = [row for row in rows if str(row.get(key)) == values[0]]
            return copy.deepcopy(rows)
        if len(parts) == 6 and endpoint == 'teams':
            return copy.deepcopy(self.data['users'])
        if len(parts) == 6 and endpoint == 'users':
            memberships = self.data.get('user_memberships', {}).get(parts[4], {})
            return copy.deepcopy(memberships.get(parts[5], self.data.get('foreign_membership', [])))
        return super().listing(path)


def ad_fixture(with_memberships=False):
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
    if with_memberships:
        d['role_definitions'] += [
            dict(id=800, name='Organization Member', managed=True, content_type='shared.organization',
                 permissions=['shared.member_organization', 'shared.view_organization', 'shared.view_team']),
            dict(id=801, name='Team Member', managed=True, content_type='shared.team',
                 permissions=['shared.member_team', 'shared.view_team']),
        ]
        d['user_memberships'] = {'500': {'organizations': [d['organizations'][0]], 'teams': d['teams'][:2]}}
        d['role_user_assignments'] = [dict(user=500, role_definition=800, object_id='1', content_type='shared.organization')]
        d['role_user_assignments'] += [dict(user=500, role_definition=801, object_id=str(team['id']), content_type='shared.team')
                                       for team in d['teams'][:2]]
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

    def test_native_managed_membership_assignments_match_verified_owned_memberships(self):
        p, d = ad_fixture(with_memberships=True)
        saved = cleanup.snapshot(p, API(d))
        self.assertEqual(len(saved['users']), 12)
        self.assertEqual(len(saved['role_definitions']), 4)
        self.assertNotIn(800, [row['id'] for row in saved['role_definitions']])
        d['authenticators'] = []
        self.assertEqual(cleanup.snapshot(dict(p, saved=saved), API(d)), saved)

    def test_direct_foreign_custom_elevated_or_resource_assignments_are_refused(self):
        for fault in ('foreign-object', 'unheld-team', 'custom-role', 'admin-role',
                      'extra-permission', 'resource-role', 'wrong-content-type', 'unknown-role'):
            p, d = ad_fixture(with_memberships=True)
            grant = d['role_user_assignments'][0]
            definition = next(row for row in d['role_definitions'] if row['id'] == 800)
            if fault == 'foreign-object': grant['object_id'] = '9999'
            if fault == 'unheld-team':
                grant.update(role_definition=801, content_type='shared.team', object_id=str(d['teams'][2]['id']))
            if fault == 'custom-role': definition['managed'] = False
            if fault == 'admin-role': definition['name'] = 'Organization Admin'
            if fault == 'extra-permission': definition['permissions'].append('shared.change_organization')
            if fault == 'resource-role': grant['role_definition'] = 700
            if fault == 'wrong-content-type': grant['content_type'] = 'awx.project'
            if fault == 'unknown-role': grant['role_definition'] = 9999
            with self.subTest(fault=fault), self.assertRaisesRegex(AssertionError, 'direct grants'):
                cleanup.snapshot(p, API(d))

    def test_regional_cleanup_accepts_users_already_removed_before_authenticator(self):
        p, d = ad_fixture(with_memberships=True)
        saved = cleanup.snapshot(p, API(d))
        before = {key: [] for key in saved if key != 'prefix'}
        before['prefix'] = p['prefix']
        d['authenticators'] = []
        for count in (5, 0):
            d['users'] = copy.deepcopy(ad_fixture()[1]['users'][:count])
            current = cleanup.snapshot(dict(p, saved=saved), API(d))
            self.assertEqual(cleanup.remaining(current, saved, before)['users'], saved['users'][:count])
            self.assertEqual(current['projects'], saved['projects'])

    def test_early_user_removal_requires_captured_id_name_and_original_baseline_exclusion(self):
        tasks = yaml.safe_load((ROOT / 'tasks/windows_remove_ldap.yml').read_text())[0]['block']
        block = next(row['block'] for row in tasks if row['name'].startswith('Remove only captured LDAP-exclusive users'))
        guard = next(row['ansible.builtin.assert']['that'] for row in block
                     if row['name'].startswith('Require every remaining user in the captured plan'))
        captured = [{'id': 500, 'username': 'example-reader'}, {'id': 501, 'username': 'example-executor'}]
        for fault in ('normal', 'partial-retry', 'foreign-id', 'changed-name', 'original-user', 'wrong-provider-name'):
            item = copy.deepcopy(captured[1 if fault == 'partial-retry' else 0])
            original = []
            provider = [copy.deepcopy(item)]
            if fault == 'foreign-id': item['id'] = 9999
            if fault == 'changed-name': item['username'] = 'foreign-reader'
            if fault == 'original-user': original = [copy.deepcopy(item)]
            if fault == 'wrong-provider-name': provider[0]['username'] = 'foreign-reader'
            values = {'item': item, 'teardown_baseline': {'ad_cleanup': {'users': captured},
                      'ad_before': {'users': original}}, 'windows_ldap_authenticator_users': {'json': {'results': provider}}}
            templar = Templar(loader=DataLoader(), variables=values)
            allowed = all(templar.template('{{ ' + expression + ' }}') for expression in guard)
            with self.subTest(fault=fault):
                self.assertEqual(allowed, fault in ('normal', 'partial-retry'))
        removal = next(row for row in block if 'ansible.platform.user' in row)
        self.assertEqual(removal['ansible.platform.user']['state'], 'absent')
        self.assertEqual(removal['ansible.platform.user']['username'], '{{ item.id | string }}')
        self.assertIn('windows_decommission_apply', removal['when'])

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
