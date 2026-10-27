# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
"""Verify scoped resource grants and inert fixed-input mock jobs locally."""

from itertools import product
from pathlib import Path
import unittest

from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment
import yaml


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_SETS = [
    {'key': 'DKlocal', 'owner': 'DK', 'access': 'DK'},
    {'key': 'NOlocal', 'owner': 'NO', 'access': 'NO'},
    {'key': 'DKEUapproved', 'owner': 'DK', 'access': 'EU'},
    {'key': 'NOEUapproved', 'owner': 'NO', 'access': 'EU'},
    {'key': 'NZlocal', 'owner': 'NZ', 'access': 'NZ'},
]


class RegionalResourceTests(unittest.TestCase):
    def setUp(self):
        self.play = yaml.safe_load((ROOT / 'configure_aap_ad_regions.yml').read_text())[0]
        self.tasks = yaml.safe_load((ROOT / 'tasks/configure_aap_ad_region.yml').read_text())
        self.mock = yaml.safe_load((ROOT / 'mock_regional_job.yml').read_text())[0]
        self.jinja = NativeEnvironment(undefined=StrictUndefined)
        self.jinja.filters['product'] = lambda left, right: list(product(left, right))
        self.jinja.filters['bool'] = bool

    def render(self, value, variables):
        return self.jinja.from_string(value).render(variables) if isinstance(value, str) else value

    def grants(self):
        """Expand actual grant tasks with synthetic inputs; no APIs or secrets."""
        grants = []
        for resource in RESOURCE_SETS:
            variables = {'active_directory': {'prefix': 'Sample'},
                         'ad_access_labels': self.play['vars']['ad_access_labels'],
                         'ad_organization': 'Sample organization', 'ad_resource_set': resource}
            for task in self.tasks:
                module = task.get('ansible.platform.role_team_assignment')
                if module is None:
                    continue
                context = dict(variables, **task.get('vars', {}))
                items = self.render(task['loop'], context) if 'loop' in task else [None]
                for item in items:
                    context['item'] = item
                    if 'when' in task and not self.jinja.compile_expression(task['when'])(context):
                        continue
                    self.assertEqual(len(module['assignment_objects']), 1)
                    obj = module['assignment_objects'][0]
                    self.assertEqual(self.render(obj['organization'], context), 'Sample organization')
                    grants.append((self.render(module['team'], context),
                                   self.render(module['role_definition'], context),
                                   self.render(obj['name'], context),
                                   self.render(obj['type'], context)))
        return grants

    def test_norway_keys_and_labels_remain_strings(self):
        labels = self.play['vars']['ad_access_labels']
        self.assertEqual(labels, {'DK': 'DKlocal', 'NO': 'NOlocal',
                                  'EU': 'EUapproved', 'NZ': 'NZlocal'})

    def test_mock_inputs_match_all_five_resource_sets(self):
        definitions = self.mock['tasks'][0]['vars']['demo_sets']
        self.assertEqual(definitions, {item['key']: {'owner': item['owner'], 'access': item['access']}
                                       for item in RESOURCE_SETS})

    def test_resource_resume_selects_only_requested_sets_and_skips_preparation(self):
        block = next(task['block'] for task in self.play['tasks'] if 'block' in task)
        resource_task = next(task for task in block if task.get('ansible.builtin.include_tasks') ==
                             'tasks/configure_aap_ad_region.yml')
        base = {'active_directory': {'resource_sets': RESOURCE_SETS},
                'ad_aap_authentication_only': False}
        for selection in (['NZlocal'], ['DKEUapproved', 'NOEUapproved']):
            context = dict(base, ad_aap_resuming_resources=True,
                           ad_aap_resume_resource_sets=selection)
            actual = self.render(resource_task['loop'], context)
            self.assertEqual([item['key'] for item in actual], selection)
            for task in block:
                if any(module in task for module in ('ansible.controller.project',
                       'ansible.controller.project_update', 'ansible.platform.team',
                       'ansible.platform.role_definition')) and task.get('ansible.controller.project', {}).get('state') != 'absent':
                    conditions = task.get('when', [])
                    self.assertIsInstance(conditions, list)
                    self.assertFalse(all(self.jinja.compile_expression(condition)(context)
                                         for condition in conditions))
        self.assertEqual(self.render(resource_task['loop'],
                                     dict(base, ad_aap_resuming_resources=False)), RESOURCE_SETS)
        inspection = next(task for task in block if task['name'].startswith('Inspect owned objects'))
        self.assertIn("'require_migrated': ad_aap_resuming_resources | bool",
                      inspection['ansible.builtin.command']['stdin'])

    def test_grant_and_authentication_retries_are_bounded(self):
        authentication = yaml.safe_load((ROOT / 'tasks/configure_aap_ad_authentication.yml').read_text())
        tasks = [task for task in self.tasks if 'ansible.platform.role_team_assignment' in task]
        tasks += [task for task in authentication if any(key.startswith('ansible.platform.') for key in task)]
        for task in tasks:
            self.assertTrue(1 <= task['retries'] <= 3)
            self.assertGreaterEqual(task['delay'], 1)
            self.assertEqual(task['until'], task['register'] + ' is succeeded')

    def test_team_migration_resolves_inspected_access_labels(self):
        block = next(task['block'] for task in self.play['tasks'] if 'block' in task)
        task = next(task for task in block if 'ansible.platform.team' in task)
        labels = self.play['vars']['ad_access_labels']
        plan = {label: {role: str(index * 3 + offset + 1)
                        for offset, role in enumerate(('reader', 'executor', 'admin'))}
                for index, label in enumerate(labels.values())}
        for access, label in labels.items():
            for role in ('reader', 'executor', 'admin'):
                context = {'item': ({'key': access, 'value': label}, role),
                           'active_directory': {'prefix': 'Sample'},
                           'ad_migration': {'teams': plan}}
                actual = self.render(task['ansible.platform.team']['name'], context)
                self.assertEqual(str(actual), plan[label][role])
                self.assertEqual(self.render(task['ansible.platform.team']['new_name'], context),
                                 'Sample ' + label + ' ' + role)

    def test_exactly_seventy_five_unique_grants_target_only_five_owned_objects_per_set(self):
        grants = self.grants()
        self.assertEqual(len(grants), 75)
        self.assertEqual(len(set(grants)), 75)
        self.assertEqual({grant[3] for grant in grants},
                         {'awx.project', 'awx.inventory', 'awx.credential', 'awx.jobtemplate'})
        for resource in RESOURCE_SETS:
            expected = {resource['key'], resource['key'] + ' Inventory',
                        resource['key'] + ' Credential', resource['key'] + ' Read',
                        resource['key'] + ' Simulate Change'}
            for role in ('reader', 'executor', 'admin'):
                team = 'Sample {} {}'.format(self.play['vars']['ad_access_labels'][resource['access']], role)
                actual = {obj for grant_team, _, obj, _ in grants if grant_team == team and obj in expected}
                self.assertEqual(actual, expected)

    def test_every_role_has_exactly_the_expected_permissions(self):
        for team, role, _, kind in self.grants():
            if team.endswith(' reader'):
                self.assertEqual(role, 'Sample {} Reader'.format(kind.split('.')[1]))
            elif team.endswith(' executor'):
                self.assertEqual(role, {'awx.project': 'Sample project Reader',
                                        'awx.inventory': 'Inventory Use',
                                        'awx.credential': 'Credential Use',
                                        'awx.jobtemplate': 'JobTemplate Execute'}[kind])
            else:
                self.assertTrue(team.endswith(' admin'))
                self.assertEqual(role, {'awx.project': 'Project Admin',
                                        'awx.inventory': 'Inventory Admin',
                                        'awx.credential': 'Credential Admin',
                                        'awx.jobtemplate': 'JobTemplate Admin'}[kind])

    def test_reader_role_definitions_contain_only_the_matching_view_permission(self):
        block = next(task['block'] for task in self.play['tasks'] if 'block' in task)
        role_task = next(task for task in block if 'ansible.platform.role_definition' in task)
        definition = role_task['ansible.platform.role_definition']
        kinds = self.render(role_task['loop'], self.play['vars'])
        self.assertEqual(set(kinds), {'project', 'inventory', 'credential', 'jobtemplate'})
        for kind in kinds:
            context = {'item': kind, 'active_directory': {'prefix': 'Sample'}}
            self.assertEqual(self.render(definition['content_type'], context), 'awx.' + kind)
            self.assertEqual([self.render(permission, context) for permission in definition['permissions']],
                             ['awx.view_' + kind])

    def test_effective_country_teams_see_only_the_accepted_resource_matrix(self):
        country_teams = {'DK': {'DKlocal', 'EUapproved'}, 'NO': {'NOlocal', 'EUapproved'},
                         'NZ': {'NZlocal'}, 'HU': {'EUapproved'}}
        expected = {'DK': {'DKlocal', 'DKEUapproved', 'NOEUapproved'},
                    'NO': {'NOlocal', 'DKEUapproved', 'NOEUapproved'},
                    'NZ': {'NZlocal'}, 'HU': {'DKEUapproved', 'NOEUapproved'}}
        grants = self.grants()
        for country, labels in country_teams.items():
            for role in ('reader', 'executor', 'admin'):
                teams = {'Sample {} {}'.format(label, role) for label in labels}
                projects = {obj for team, _, obj, kind in grants if team in teams and kind == 'awx.project'}
                with self.subTest(country=country, role=role):
                    self.assertEqual(projects, expected[country])

    def test_mock_templates_fix_resource_dependencies_and_disable_input_prompts(self):
        template = next(task['ansible.controller.job_template'] for task in self.tasks
                        if 'ansible.controller.job_template' in task)
        self.assertEqual(template['project'], '{{ ad_resource_set.key }}')
        self.assertEqual(template['inventory'], '{{ ad_resource_set.key }} Inventory')
        self.assertEqual(template['credentials'], ['{{ ad_resource_set.key }} Credential'])
        self.assertEqual(template['playbook'], 'mock_regional_job.yml')
        self.assertEqual(template['extra_vars'], {
            'demo_resource_set': '{{ ad_resource_set.key }}',
            'demo_owner': '{{ ad_resource_set.owner }}',
            'demo_access': '{{ ad_resource_set.access }}',
            'demo_operation': '{{ item.key }}',
        })
        for flag in ('ask_inventory_on_launch', 'ask_credential_on_launch',
                     'ask_variables_on_launch', 'ask_scm_branch_on_launch',
                     'ask_job_type_on_launch', 'ask_limit_on_launch',
                     'ask_tags_on_launch', 'ask_skip_tags_on_launch',
                     'ask_execution_environment_on_launch', 'survey_enabled'):
            with self.subTest(flag=flag):
                self.assertIs(template.get(flag), False)

    def test_mock_jobs_have_an_enabled_local_host_and_only_controller_side_inert_tasks(self):
        host = next(task['ansible.controller.host'] for task in self.tasks if 'ansible.controller.host' in task)
        self.assertEqual(host['name'], 'localhost')
        self.assertIs(host['enabled'], True)
        self.assertEqual(host['variables']['ansible_connection'], 'local')
        self.assertEqual(self.mock['connection'], 'local')
        self.assertIs(self.mock['gather_facts'], False)
        modules = {key for task in self.mock['tasks'] for key in task if key.startswith('ansible.')}
        self.assertEqual(modules, {'ansible.builtin.assert', 'ansible.builtin.debug'})

    def test_ldap_maps_revoke_stale_membership_and_assign_only_membership_roles(self):
        tasks = yaml.safe_load((ROOT / 'tasks/configure_aap_ad_authentication.yml').read_text())
        maps = [task['ansible.platform.authenticator_map'] for task in tasks
                if 'ansible.platform.authenticator_map' in task]
        self.assertEqual({item['map_type'] for item in maps}, {'allow', 'organization', 'team'})
        self.assertTrue(all(item['revoke'] is True for item in maps))
        organization = next(item for item in maps if item['map_type'] == 'organization')
        self.assertEqual(organization['role'], 'Organization Member')
        team_task = next(task for task in tasks
                         if task.get('ansible.platform.authenticator_map', {}).get('map_type') == 'team')
        self.assertEqual(team_task['ansible.platform.authenticator_map']['role'], 'Team Member')
        self.assertIn("selectattr('scope', 'equalto', 'DomainLocal')", team_task['loop'])
        self.assertEqual(team_task['ansible.platform.authenticator_map']['triggers']['groups']['has_or'],
                         ["{{ ('CN=' ~ item.name ~ ',' ~ item.path) | lower }}"])
        authenticators = [task['ansible.platform.authenticator'] for task in tasks
                          if 'ansible.platform.authenticator' in task]
        self.assertEqual(authenticators[0]['configuration']['GROUP_TYPE'], 'NestedActiveDirectoryGroupType')
        self.assertEqual(authenticators[0]['configuration']['CONNECTION_OPTIONS']['OPT_X_TLS_REQUIRE_CERT'], 2)


if __name__ == '__main__':
    unittest.main()
