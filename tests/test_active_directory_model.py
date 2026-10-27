# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
"""Verify the effective access matrix without Windows or AAP dependencies."""

import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys
import unittest

SPEC = importlib.util.spec_from_file_location(
    'ad_model', Path(__file__).parents[1] / 'assets/active-directory-model.py')
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


class RegionalAccessTests(unittest.TestCase):
    def setUp(self):
        self.model = MODEL.model('Synthetic', 'example.test')
        self.groups = {item['name']: item for item in self.model['groups']}

    def access(self, region, role):
        memberships = {'Synthetic-GG-{}-{}'.format(region, role)}
        while True:
            expanded = memberships | {name for name, group in self.groups.items()
                                       if memberships.intersection(group['members'])}
            if expanded == memberships:
                break
            memberships = expanded
        return {(group['region'], group['role']) for name, group in self.groups.items()
                if name in memberships and group['scope'] == 'DomainLocal'}

    def test_cohort_has_twelve_unique_users_and_twenty_four_unique_groups(self):
        users = self.model['users']
        self.assertEqual(len(users), 12)
        self.assertEqual(len({user['username'] for user in users}), 12)
        self.assertEqual(len(self.model['groups']), 24)
        self.assertEqual(len(self.groups), 24)
        self.assertEqual({user['region'] for user in users}, {'DK', 'NO', 'NZ', 'HU'})
        self.assertEqual({(user['region'], user['role']) for user in users},
                         {(region, role) for region in ('DK', 'NO', 'NZ', 'HU')
                          for role in ('reader', 'executor', 'admin')})

    def test_each_country_receives_only_its_matching_role_and_eu_role(self):
        for region in ('DK', 'NO'):
            for role in ('reader', 'executor', 'admin'):
                with self.subTest(region=region, role=role):
                    self.assertEqual(self.access(region, role), {(region, role), ('EU', role)})

    def test_new_zealand_never_inherits_european_access(self):
        for role in ('reader', 'executor', 'admin'):
            self.assertEqual(self.access('NZ', role), {('NZ', role)})

    def test_hungary_receives_only_eu_approved_access(self):
        for role in ('reader', 'executor', 'admin'):
            self.assertEqual(self.access('HU', role), {('EU', role)})
        self.assertFalse(any(group['scope'] == 'DomainLocal' and group['region'] == 'HU'
                             for group in self.model['groups']))

    def test_no_role_inherits_a_more_privileged_role(self):
        for region in ('DK', 'NO', 'NZ', 'HU'):
            for role in ('reader', 'executor', 'admin'):
                with self.subTest(region=region, role=role):
                    self.assertEqual({item[1] for item in self.access(region, role)}, {role})

    def test_resource_sets_have_country_owners_and_explicit_access_scopes(self):
        self.assertEqual(self.model['resource_sets'], [
            {'key': 'DKlocal', 'owner': 'DK', 'access': 'DK'},
            {'key': 'NOlocal', 'owner': 'NO', 'access': 'NO'},
            {'key': 'DKEUapproved', 'owner': 'DK', 'access': 'EU'},
            {'key': 'NOEUapproved', 'owner': 'NO', 'access': 'EU'},
            {'key': 'NZlocal', 'owner': 'NZ', 'access': 'NZ'},
        ])

    def test_complete_matrix_including_both_eu_approved_country_sets(self):
        expected = {
            'DK': {'DKlocal', 'DKEUapproved', 'NOEUapproved'},
            'NO': {'NOlocal', 'DKEUapproved', 'NOEUapproved'},
            'NZ': {'NZlocal'},
            'HU': {'DKEUapproved', 'NOEUapproved'},
        }
        for user in self.model['users']:
            effective = self.access(user['region'], user['role'])
            resources = {item['key'] for item in self.model['resource_sets']
                         if (item['access'], user['role']) in effective}
            with self.subTest(region=user['region'], role=user['role']):
                self.assertEqual(resources, expected[user['region']])

    def test_members_reference_only_the_matching_country_role_groups(self):
        for group in self.model['groups']:
            for member in group['members']:
                with self.subTest(group=group['name'], member=member):
                    self.assertIn(member, self.groups)
                    self.assertEqual(self.groups[member]['scope'], 'Global')
                    self.assertEqual(self.groups[member]['role'], group['role'])
        for user in self.model['users']:
            group = self.groups[user['group']]
            self.assertEqual((group['region'], group['role'], group['scope']),
                             (user['region'], user['role'], 'Global'))

    def test_only_the_old_eu_cohort_is_retired_without_password_material(self):
        expected_roles = {'reader', 'executor', 'admin'}
        retired_users = self.model['retired_users']
        retired_groups = self.model['retired_groups']
        self.assertEqual(len(retired_users), 3)
        self.assertEqual(len(retired_groups), 3)
        self.assertEqual({item['role'] for item in retired_users}, expected_roles)
        self.assertEqual({item['role'] for item in retired_groups}, expected_roles)
        for item in retired_users:
            self.assertEqual(set(item), {'username', 'path', 'region', 'role'})
            self.assertEqual(item['username'], 'synthetic-eu-' + item['role'])
            self.assertEqual(item['path'], 'OU=EU,' + self.model['root_dn'])
            self.assertEqual(item['region'], 'EU')
            self.assertNotIn(item['username'], {user['username'] for user in self.model['users']})
        for item in retired_groups:
            self.assertEqual(item['name'], 'Synthetic-GG-EU-' + item['role'])
            self.assertEqual(item['path'], 'OU=EU,' + self.model['root_dn'])
            self.assertEqual((item['scope'], item['region']), ('Global', 'EU'))
            self.assertNotIn(item['name'], self.groups)
            self.assertIn('Synthetic-DL-EU-' + item['role'], self.groups)

    def test_eu_access_ou_is_preserved_and_hungary_ou_is_added(self):
        self.assertEqual(self.model['root_dn'], 'OU=Synthetic,DC=example,DC=test')
        ous = {item['name']: item['path'] for item in self.model['ous']}
        self.assertEqual(set(ous), {'Synthetic', 'DK', 'NO', 'EU', 'NZ', 'HU'})
        self.assertEqual(ous['EU'], self.model['root_dn'])
        self.assertEqual(ous['HU'], self.model['root_dn'])

    def test_norway_and_country_labels_remain_strings(self):
        norwegian_users = [user for user in self.model['users'] if user['region'] == 'NO']
        self.assertEqual(len(norwegian_users), 3)
        self.assertTrue(all(user['region_label'] == 'Norway' for user in norwegian_users))
        self.assertTrue(all(isinstance(group['region'], str) for group in self.model['groups']))

    def test_model_calls_do_not_share_mutable_members_or_resources(self):
        self.model['resource_sets'][0]['access'] = 'changed'
        self.model['groups'][0]['members'].append('changed')
        fresh = MODEL.model('Synthetic', 'example.test')
        self.assertEqual(fresh['resource_sets'][0]['access'], 'DK')
        self.assertEqual(fresh['groups'][0]['members'], [])


class ProfileGenerationTests(unittest.TestCase):
    script = Path(__file__).parents[1] / 'assets/generate-active-directory-profile.py'

    def generate(self, **extra):
        seed = {'prefix': 'Sample', 'dns_domain': 'example.test',
                'hostname': 'directory', 'netbios': 'EXAMPLE',
                'bootstrap_password': secrets.token_urlsafe(32) + 'aA1!'}
        seed.update(extra)
        return subprocess.run([sys.executable, str(self.script)], input=json.dumps(seed),
                              text=True, capture_output=True, check=False)

    def test_fresh_profile_has_five_independent_mock_passwords_and_no_retired_passwords(self):
        result = self.generate()
        self.assertEqual(result.returncode, 0, result.stderr)
        profile = json.loads(result.stdout)
        self.assertEqual(len(profile['users']), 12)
        self.assertEqual(set(profile['mock_passwords']),
                         {'DKlocal', 'NOlocal', 'DKEUapproved', 'NOEUapproved', 'NZlocal'})
        self.assertEqual(len(set(profile['mock_passwords'].values())), 5)
        self.assertEqual(len({user['password'] for user in profile['users']}), 12)
        self.assertTrue(all('password' not in user for user in profile['retired_users']))
        self.assertTrue(profile['ca_certificate'].startswith('-----BEGIN CERTIFICATE-----'))
        self.assertTrue(profile['ca_private_key_encrypted'].startswith('-----BEGIN ENCRYPTED PRIVATE KEY-----'))
        self.assertEqual(profile['domain_admin_password'], profile['bootstrap_password'])

    def test_original_image_password_is_required_for_fresh_domain_administrator(self):
        result = self.generate(bootstrap_password='')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_protected_derivation_input_is_used_and_removed_from_the_profile(self):
        suffix = secrets.token_urlsafe(12)
        result = self.generate(allow_simple_demo_passwords=True, demo_user_password_suffix=suffix)
        self.assertEqual(result.returncode, 0, result.stderr)
        profile = json.loads(result.stdout)
        self.assertNotIn('demo_user_password_suffix', profile)
        self.assertTrue(all(user['password'] == user['username'] + suffix
                            for user in profile['users']))

    def test_derivation_requires_explicit_scoped_policy_and_nonempty_string_input(self):
        for extra in ({'demo_user_password_suffix': secrets.token_urlsafe(12)},
                      {'allow_simple_demo_passwords': True, 'demo_user_password_suffix': ''},
                      {'allow_simple_demo_passwords': True, 'demo_user_password_suffix': 1}):
            result = self.generate(**extra)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
