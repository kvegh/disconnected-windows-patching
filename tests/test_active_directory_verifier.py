# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
"""Offline acceptance checks for the AD/AAP verifier, including failed-run cleanup."""

import importlib.util
from pathlib import Path
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

SPEC = importlib.util.spec_from_file_location(
    'ad_verifier', Path(__file__).resolve().parents[1] / 'assets/verify-aap-ad-regions.py')
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)

SETS = [('DKlocal', 'DK', 'DK'), ('NOlocal', 'NO', 'NO'),
        ('DKEUapproved', 'DK', 'EU'), ('NOEUapproved', 'NO', 'EU'), ('NZlocal', 'NZ', 'NZ')]
ALLOWED = {'DK': {'DKlocal', 'DKEUapproved', 'NOEUapproved'},
           'NO': {'NOlocal', 'DKEUapproved', 'NOEUapproved'},
           'NZ': {'NZlocal'}, 'HU': {'DKEUapproved', 'NOEUapproved'}}
TEAMS = {'DK': ['DKlocal', 'EUapproved'], 'NO': ['NOlocal', 'EUapproved'],
         'NZ': ['NZlocal'], 'HU': ['EUapproved']}


class FakeAAP:
    def __init__(self):
        self.profile = {'prefix': 'Demo', 'verify_logins': True,
                        'convergence_timeout': 0, 'job_wait_timeout': 0,
                        'resource_sets': [dict(key=key, owner=owner, access=access)
                                          for key, owner, access in SETS],
                        'users': [dict(region=country, role=role,
                                       username='demo-' + country.lower() + '-' + role,
                                       password='test-only-placeholder')
                                  for country in ALLOWED for role in ('reader', 'executor', 'admin')],
                        'retired_users': [dict(username='demo-eu-' + role)
                                          for role in ('reader', 'executor', 'admin')]}
        self.by_username = {user['username']: user for user in self.profile['users']}
        self.user_ids = {user['username']: index + 50 for index, user in enumerate(self.profile['users'])}
        self.id_users = {value: self.by_username[key] for key, value in self.user_ids.items()}
        self.teams = []
        self.grants = {}
        self.definitions = []
        self.resources = {kind: [] for kind in ('inventory', 'credential', 'project', 'jobtemplate')}
        self.by_resource_id = {}
        self.operation = {}
        self.credentials = {}
        self.calls = []
        self.jobs = {}
        self.drained = set()
        self.stats_read = set()
        self.fault = None
        self._fixtures()

    def _fixtures(self):
        definitions = {}

        def role_id(kind, level):
            name = ('Demo ' + kind + ' Reader' if level == 'reader' or
                    (level == 'executor' and kind == 'project') else
                    {'inventory': 'Inventory', 'credential': 'Credential', 'project': 'Project',
                     'jobtemplate': 'JobTemplate'}[kind] + ' ' +
                    ('Admin' if level == 'admin' else 'Execute' if kind == 'jobtemplate' else 'Use'))
            if name not in definitions:
                definition = dict(id=len(definitions) + 1, name=name, content_type='awx.' + kind,
                                  permissions=['awx.view_' + kind] if name.endswith(' Reader') else
                                  ['awx.view_' + kind, 'awx.change_' + kind])
                definitions[name] = definition
                self.definitions.append(definition)
            return definitions[name]['id']

        for key, owner, access in SETS:
            local = {}
            for kind, suffix in [('inventory', ' Inventory'), ('credential', ' Credential'),
                                 ('project', '')]:
                obj = dict(id=len(self.by_resource_id) + 1000, name=key + suffix,
                           organization=1, description='Fixture resource.')
                if kind == 'project':
                    obj.update(scm_type='git', scm_branch='main', scm_update_on_launch=False,
                               scm_url='https://github.com/kvegh/disconnected-windows-patching.git')
                if kind == 'inventory':
                    obj['variables'] = {'ansible_connection': 'local'}
                if kind == 'credential':
                    obj.update(credential_type=1, inputs=dict(username='Demo-mock-' + key.lower(),
                                                            password='$encrypted$'))
                self.resources[kind].append(obj)
                self.by_resource_id[obj['id']] = (key, kind, obj)
                local[kind] = obj
            for operation, label in [('read', 'Read'), ('simulate_change', 'Simulate Change')]:
                obj = dict(id=len(self.by_resource_id) + 1000, name=key + ' ' + label,
                           organization=1, description='Fixture template.', playbook='mock_regional_job.yml',
                           job_type='run', inventory=local['inventory']['id'], project=local['project']['id'],
                           ask_inventory_on_launch=False, ask_credential_on_launch=False,
                           ask_variables_on_launch=False, survey_enabled=False,
                           extra_vars=dict(demo_resource_set=key, demo_owner=owner,
                                           demo_access=access, demo_operation=operation))
                self.resources['jobtemplate'].append(obj)
                self.by_resource_id[obj['id']] = (key, 'jobtemplate', obj)
                self.operation[obj['id']] = operation
                self.credentials[obj['id']] = [local['credential']]
        for label, keys in [('DKlocal', {'DKlocal'}), ('NOlocal', {'NOlocal'}),
                            ('EUapproved', {'DKEUapproved', 'NOEUapproved'}), ('NZlocal', {'NZlocal'})]:
            for level in ('reader', 'executor', 'admin'):
                team = dict(id=len(self.teams) + 10, name='Demo ' + label + ' ' + level)
                self.teams.append(team)
                self.grants[team['id']] = [dict(team=team['id'], object_id=obj['id'],
                                                   role_definition=role_id(kind, level))
                                                 for key, kind, obj in self.by_resource_id.values()
                                                 if key in keys]

    def request(self, path, user=None, method='GET', body=None):
        parsed = urlsplit(path)
        query = parse_qs(parsed.query)
        service = 'gateway/v1' if '/gateway/' in path else 'controller/v2'
        parts = parsed.path.removeprefix('/api/' + service + '/').strip('/').split('/')
        self.calls.append((path, user['username'] if user else None, method))
        kind = {'inventories': 'inventory', 'credentials': 'credential', 'projects': 'project',
                'job_templates': 'jobtemplate'}.get(parts[0])
        if parts[0] == 'organizations':
            return 200, {'results': [dict(id=1, name='Demo Regional Identity Demo')]}
        if parts[0] == 'role_definitions':
            return 200, {'results': self.definitions}
        if parts[0] == 'credential_types':
            return 200, {'results': [dict(id=1, name='Machine', kind='ssh')]}
        if parts[0] == 'role_team_assignments':
            return 200, {'results': self.grants[int(query['team'][0])]}
        if parts[0] == 'role_user_assignments':
            return 200, {'results': []}
        if parts[0] == 'teams':
            return 200, {'results': self.teams}
        if parts[0] == 'users':
            if len(parts) == 1:
                return 200, {'results': [dict(id=999)] if self.fault == 'retired' and
                             service == 'controller/v2' else []}
            actor = self.id_users[int(parts[1])]
            names = {'Demo ' + label + ' ' + actor['role'] for label in TEAMS[actor['region']]}
            rows = [team for team in self.teams if team['name'] in names]
            if self.fault == 'team_leak':
                rows = rows + [dict(id=999, name='Forbidden team')]
            return 200, {'results': rows}
        if parts[0] == 'me':
            return 200, {'results': [dict(id=self.user_ids[user['username']], username=user['username'],
                                         is_superuser=False, is_system_auditor=False,
                                         is_platform_auditor=self.fault == 'auditor')]}
        if parts[0] == 'jobs':
            job_id = int(parts[1])
            job = self.jobs[job_id]
            if len(parts) == 2:
                self.drained.add(job_id)
                return 200, dict(job, status='failed' if self.fault == 'failed_job' and
                                 job_id == min(self.jobs) else 'successful')
            self.stats_read.add(job_id)
            stats = dict(processed={'localhost': 1}, ok={'localhost': 2}, failures={}, dark={},
                         changed={'localhost': int(job['operation'] == 'simulate_change')})
            if self.fault == 'no_tasks':
                stats.update(processed={}, ok={})
            return 200, {'results': [dict(event_data=stats)]}
        if kind and len(parts) == 1:
            rows = self.resources[kind]
            if user:
                allowed = ALLOWED[user['region']]
                rows = [obj for obj in rows if self.by_resource_id[obj['id']][0] in allowed]
                if self.fault == 'list_leak':
                    rows = rows + [dict(id=999, name='Forbidden object')]
            return 200, {'results': rows}
        if kind:
            key, _, obj = self.by_resource_id[int(parts[1])]
            if len(parts) == 3 and parts[2] == 'hosts':
                return 200, {'results': [dict(id=1, name='localhost', enabled=True,
                                             variables={'ansible_connection': 'local'})]}
            if len(parts) == 3 and parts[2] == 'credentials':
                return 200, {'results': self.credentials[obj['id']]}
            allowed = not user or key in ALLOWED[user['region']]
            if len(parts) == 3 and parts[2] == 'launch':
                permitted = allowed and user['role'] in ('executor', 'admin')
                if permitted or self.fault == 'forbidden_launch':
                    job_id = len(self.jobs) + 1
                    self.jobs[job_id] = dict(id=job_id, inventory=obj['inventory'], project=obj['project'],
                                             job_template=obj['id'], operation=self.operation[obj['id']])
                    return 201, dict(job=job_id)
                return 403, {}
            if self.fault == 'late_get_leak' and user and user['region'] == 'DK' and \
                    user['role'] == 'executor' and key == 'NOlocal':
                return 200, obj
            if method == 'PATCH':
                return (200, obj) if allowed and user['role'] == 'admin' else (403, {})
            return (200, obj) if allowed else (404, {})
        raise AssertionError('Unhandled fixture route: ' + parsed.path)


class ActiveDirectoryVerifierTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAAP()

    def run_verifier(self):
        return VERIFIER.verify_with_request(self.api.profile, self.api.request)

    def test_complete_matrix_checks_both_operations_and_local_execution(self):
        result = self.run_verifier()
        for field, value in [('object_scoped_grants_verified', 75), ('ldap_logins_verified', 12),
                             ('permission_checks', 360), ('mock_jobs_verified', 36),
                             ('localhost_execution_verified', 36), ('description_patch_checks', 108),
                             ('resource_list_checks', 48), ('team_membership_checks', 24),
                             ('retired_users_absent', 3)]:
            self.assertEqual(result[field], value, field)
        self.assertEqual(self.api.drained, set(self.api.jobs))
        self.assertEqual({job['operation'] for job in self.api.jobs.values()}, {'read', 'simulate_change'})

    def test_configuration_only_still_checks_retirement_and_every_grant(self):
        self.api.profile['verify_logins'] = False
        result = self.run_verifier()
        self.assertEqual(result['object_scoped_grants_verified'], 75)
        self.assertEqual(result['permission_checks'], 0)
        self.assertFalse(self.api.jobs)

    def test_profile_cannot_expand_country_clearance(self):
        self.api.profile['resource_sets'][0]['access'] = 'EU'
        with self.assertRaisesRegex(AssertionError, 'resource-set model'):
            self.run_verifier()
        self.assertFalse(self.api.calls)

    def test_second_template_binding_checked_before_any_launch(self):
        self.api.resources['jobtemplate'][1]['inventory'] = 999
        with self.assertRaisesRegex(AssertionError, 'fixed local inventory'):
            self.run_verifier()
        self.assertFalse(self.api.jobs)

    def test_remote_inventory_or_real_credential_is_rejected_before_launch(self):
        for kind in ('inventory', 'credential'):
            with self.subTest(kind=kind):
                self.api = FakeAAP()
                obj = self.api.resources[kind][0]
                if kind == 'inventory':
                    obj['variables']['ansible_connection'] = 'winrm'
                else:
                    obj['inputs']['username'] = 'unrelated-account-placeholder'
                with self.assertRaises(AssertionError):
                    self.run_verifier()
                self.assertFalse(self.api.jobs)

    def test_executor_project_permission_must_be_the_custom_reader(self):
        team = next(team for team in self.api.teams if team['name'] == 'Demo DKlocal executor')
        project = self.api.resources['project'][0]
        grant = next(grant for grant in self.api.grants[team['id']] if grant['object_id'] == project['id'])
        definition = next(row for row in self.api.definitions if row['id'] == grant['role_definition'])
        definition['permissions'].append('awx.use_project')
        with self.assertRaisesRegex(AssertionError, 'view-only'):
            self.run_verifier()

    def test_retired_identity_on_controller_fails_without_launching(self):
        self.api.fault = 'retired'
        with self.assertRaisesRegex(AssertionError, 'retired EU-only identity'):
            self.run_verifier()
        self.assertFalse(self.api.jobs)

    def test_unexpected_membership_and_list_visibility_are_rejected(self):
        for fault, message in [('team_leak', 'team membership'), ('list_leak', 'forbidden or duplicate'),
                               ('auditor', 'global privilege')]:
            with self.subTest(fault=fault):
                self.api = FakeAAP()
                self.api.fault = fault
                with self.assertRaisesRegex(AssertionError, message):
                    self.run_verifier()

    def test_failed_access_check_still_drains_already_launched_jobs(self):
        self.api.fault = 'late_get_leak'
        with self.assertRaisesRegex(AssertionError, 'forbidden country resource'):
            self.run_verifier()
        self.assertEqual(len(self.api.jobs), 2)
        self.assertEqual(self.api.drained, set(self.api.jobs))
        self.assertEqual(self.api.stats_read, set(self.api.jobs))

    def test_unexpected_forbidden_launch_is_also_drained(self):
        self.api.fault = 'forbidden_launch'
        with self.assertRaisesRegex(AssertionError, 'launch violated'):
            self.run_verifier()
        self.assertEqual(len(self.api.jobs), 1)
        self.assertEqual(self.api.drained, {1})

    def test_success_status_without_host_tasks_is_rejected_after_draining_every_job(self):
        self.api.fault = 'no_tasks'
        with self.assertRaisesRegex(AssertionError, 'execute its tasks on localhost'):
            self.run_verifier()
        self.assertEqual(len(self.api.jobs), 36)
        self.assertEqual(self.api.drained, set(self.api.jobs))

    def test_one_failed_job_does_not_stop_draining_other_jobs(self):
        self.api.fault = 'failed_job'
        with self.assertRaisesRegex(AssertionError, 'did not complete successfully'):
            self.run_verifier()
        self.assertEqual(len(self.api.jobs), 36)
        self.assertEqual(self.api.drained, set(self.api.jobs))
        self.assertEqual(len(self.api.stats_read), 35)


if __name__ == '__main__':
    unittest.main()
