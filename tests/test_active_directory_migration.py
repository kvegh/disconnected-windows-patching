"""Exercise migration ownership and retirement guards without contacting AAP."""

import copy
import importlib.util
from pathlib import Path
import secrets
import unittest
from unittest.mock import patch
import urllib.parse


SPEC = importlib.util.spec_from_file_location(
    'ad_migration', Path(__file__).parents[1] / 'assets/inspect-aap-ad-migration.py')
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)
PREFIX = 'Example'


def fixture(migrated=False, keep_old_project=True):
    data = {
        'organizations': [{'id': 1, 'name': PREFIX + ' Regional Identity Demo'}],
        'inventories': [], 'credentials': [], 'job_templates': [], 'projects': [],
        'teams': [], 'authenticators': [{'id': 7, 'name': PREFIX + ' Active Directory',
                                      'type': MIGRATION.LDAP_TYPE}],
        'users': [], 'workflow_job_template_nodes': [], 'links': {},
    }
    if keep_old_project:
        data['projects'].append({
            'id': 2, 'organization': 1, 'name': PREFIX + ' Regional Mock Resources',
            'scm_type': 'git', 'scm_url': MIGRATION.SOURCE_URL, 'scm_branch': 'main',
        })
    for index, key in enumerate(MIGRATION.RESOURCE_SETS):
        if not migrated and key not in MIGRATION.LEGACY_RESOURCE_LABELS:
            continue
        inventory_id = 10 + index * 10
        credential_id = inventory_id + 1
        project_id = 100 + index if migrated else 2
        if migrated:
            data['projects'].append({
                'id': project_id, 'organization': 1, 'name': key,
                'scm_type': 'git', 'scm_url': MIGRATION.SOURCE_URL, 'scm_branch': 'main',
            })
        for kind, endpoint in (('inventory', 'inventories'), ('credential', 'credentials'),
                               ('read', 'job_templates'), ('simulate_change', 'job_templates')):
            suffix = MIGRATION.SUFFIXES[kind][0 if migrated else 1]
            label = key if migrated else PREFIX + ' ' + MIGRATION.LEGACY_RESOURCE_LABELS[key]
            item = {'id': inventory_id + list(MIGRATION.SUFFIXES).index(kind),
                    'name': label + ' ' + suffix, 'organization': 1}
            if kind in ('read', 'simulate_change'):
                item.update(inventory=inventory_id, project=project_id,
                            playbook='mock_regional_job.yml')
                data['links'][str(item['id'])] = [{'id': credential_id, 'organization': 1}]
            data[endpoint].append(item)
    for index, (scope, legacy) in enumerate(MIGRATION.TEAM_SCOPES.items()):
        for role_index, role in enumerate(MIGRATION.ROLES):
            data['teams'].append({
                'id': 300 + 10 * index + role_index, 'organization': 1,
                'name': PREFIX + ' ' + (scope if migrated else legacy) + ' ' + role,
            })
    for index, role in enumerate(MIGRATION.ROLES):
        username = PREFIX.lower() + '-eu-' + role
        data['users'].append({
            'id': 400 + index, 'username': username, 'is_superuser': False,
            'is_platform_auditor': False, 'associated_authenticators': {'7': {'uid': username}},
        })
    return data


class FixtureAPI:
    """Apply actual query filters so foreign references test global guards."""

    def __init__(self, data):
        self.data = data

    def listing(self, path):
        parsed = urllib.parse.urlsplit(path)
        parts = parsed.path.strip('/').split('/')
        endpoint = parts[3]
        if endpoint == 'job_templates' and len(parts) == 6:
            return copy.deepcopy(self.data['links'][parts[4]])
        values = self.data[endpoint]
        query = urllib.parse.parse_qs(parsed.query)
        for key in ('organization', 'project', 'unified_job_template', 'username', 'name'):
            if key in query:
                values = [item for item in values if str(item.get(key)) == query[key][0]]
        return copy.deepcopy(values)


class ActiveDirectoryMigrationTests(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'url': 'https://platform.example.test', 'ca': 'Synthetic fixture CA',
            'admin_username': 'fixture-admin', 'admin_password': secrets.token_urlsafe(16),
            'prefix': PREFIX, 'authenticator_name': PREFIX + ' Active Directory',
        }

    def inspect(self, data, require_migrated=False):
        with patch.object(MIGRATION, 'API', lambda parameters, ca: FixtureAPI(data)):
            return MIGRATION.inspect(dict(self.parameters, require_migrated=require_migrated))

    def test_legacy_plan_reuses_ids_and_retires_only_three_owned_eu_users(self):
        plan = self.inspect(fixture())
        self.assertEqual(sum(value.isdigit() for resource in plan['resources'].values()
                             for value in resource.values()), 16)
        self.assertEqual(plan['resources']['DKEUapproved']['inventory'], '30')
        self.assertEqual(plan['resources']['NOEUapproved']['inventory'], 'NOEUapproved Inventory')
        self.assertTrue(all(value.isdigit() for team in plan['teams'].values() for value in team.values()))
        self.assertEqual(plan['retired_users'], ['400', '401', '402'])
        self.assertEqual(plan['retired_usernames'],
                         ['example-eu-reader', 'example-eu-executor', 'example-eu-admin'])

    def test_completed_migration_can_be_inspected_repeatedly(self):
        data = fixture(migrated=True, keep_old_project=False)
        plan = self.inspect(data, require_migrated=True)
        self.assertEqual(plan, self.inspect(data, require_migrated=True))
        self.assertIsNone(plan['old_project'])
        self.assertTrue(all(value.isdigit() for resource in plan['resources'].values()
                            for value in resource.values()))

    def test_missing_organization_returns_only_desired_new_names(self):
        data = fixture()
        data['organizations'] = []
        plan = self.inspect(data)
        self.assertEqual(plan['resources']['DKlocal']['inventory'], 'DKlocal Inventory')
        self.assertEqual(plan['teams']['EUapproved']['reader'], PREFIX + ' EUapproved reader')
        self.assertEqual(plan['retired_users'], [])
        self.assertEqual(plan['retired_usernames'], [])
        self.assertIsNone(plan['old_project'])

    def test_legacy_resource_names_cannot_pass_final_migration_guard(self):
        with self.assertRaisesRegex(AssertionError, 'legacy name'):
            self.inspect(fixture(), require_migrated=True)

    def test_old_and_new_names_for_one_resource_are_ambiguous(self):
        data = fixture()
        item = dict(data['inventories'][0], id=999, name='DKlocal Inventory')
        data['inventories'].append(item)
        with self.assertRaisesRegex(AssertionError, 'candidates exist'):
            self.inspect(data)

    def test_foreign_organization_object_is_rejected_even_if_api_filter_misbehaves(self):
        class IncorrectlyFilteredAPI:
            def listing(self, path):
                return [{'id': 999, 'organization': 2, 'name': 'DKlocal Inventory'}]

        with self.assertRaisesRegex(AssertionError, 'differently owned'):
            MIGRATION.owned_listing(IncorrectlyFilteredAPI(), 'inventories', '1',
                                    {'DKlocal Inventory'}, 'inventory')

    def test_unexpected_object_in_owned_organization_is_rejected(self):
        data = fixture()
        data['inventories'][0]['name'] = 'Unrelated Inventory'
        with self.assertRaisesRegex(AssertionError, 'unexpected'):
            self.inspect(data)

    def test_project_requires_reviewed_public_source_and_main_branch(self):
        for key, value in (('scm_url', 'https://example.test/unreviewed.git'),
                           ('scm_branch', 'unreviewed'), ('scm_type', 'manual')):
            with self.subTest(key=key):
                data = fixture()
                data['projects'][0][key] = value
                with self.assertRaisesRegex(AssertionError, 'approved public Git source'):
                    self.inspect(data)

    def test_final_template_cannot_keep_shared_project(self):
        data = fixture(migrated=True)
        data['job_templates'][0]['project'] = 2
        with self.assertRaisesRegex(AssertionError, 'owned mock project'):
            self.inspect(data, require_migrated=True)

    def test_template_cannot_reference_other_resource_set_inventory(self):
        data = fixture()
        data['job_templates'][0]['inventory'] = 20
        with self.assertRaisesRegex(AssertionError, 'resource-set inventory'):
            self.inspect(data)

    def test_template_cannot_reference_other_resource_set_credential(self):
        data = fixture()
        data['links'][str(data['job_templates'][0]['id'])] = [{'id': 21, 'organization': 1}]
        with self.assertRaisesRegex(AssertionError, 'owned mock credential'):
            self.inspect(data)

    def test_privileged_user_is_never_selected_for_retirement(self):
        for flag in ('is_superuser', 'is_platform_auditor', 'is_system_auditor'):
            with self.subTest(flag=flag):
                data = fixture()
                data['users'][0][flag] = True
                with self.assertRaisesRegex(AssertionError, 'LDAP-user safeguards'):
                    self.inspect(data)

    def test_user_from_another_authenticator_is_never_selected_for_retirement(self):
        data = fixture()
        data['users'][0]['associated_authenticators'] = {'8': {}}
        with self.assertRaisesRegex(AssertionError, 'LDAP-user safeguards'):
            self.inspect(data)

    def test_unused_shared_project_can_be_retired_after_migration(self):
        plan = self.inspect(fixture(migrated=True), require_migrated=True)
        self.assertEqual(plan['old_project'], '2')

    def test_foreign_template_reference_prevents_shared_project_retirement(self):
        data = fixture(migrated=True)
        data['job_templates'].append({'id': 999, 'organization': 2, 'project': 2})
        with self.assertRaisesRegex(AssertionError, 'still has template or workflow references'):
            self.inspect(data, require_migrated=True)

    def test_workflow_reference_prevents_shared_project_retirement(self):
        data = fixture(migrated=True)
        data['workflow_job_template_nodes'].append({'id': 999, 'unified_job_template': 2})
        with self.assertRaisesRegex(AssertionError, 'still has template or workflow references'):
            self.inspect(data, require_migrated=True)

    def test_final_guard_requires_existing_organization(self):
        data = fixture()
        data['organizations'] = []
        with self.assertRaisesRegex(AssertionError, 'final demo organization is missing'):
            self.inspect(data, require_migrated=True)


if __name__ == '__main__':
    unittest.main()
