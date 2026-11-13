"""Reproduce the two normal initial-run guards using native Ansible."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run_play(play, extra_files=None, environment=None):
    with tempfile.TemporaryDirectory(prefix='windows-initial-run-') as directory:
        path = Path(directory)
        for name, value in (extra_files or {}).items():
            (path / name).write_text(yaml.safe_dump(value))
        (path / 'main.yml').write_text(yaml.safe_dump(play))
        env = dict(os.environ, ANSIBLE_FILTER_PLUGINS=str(ROOT / 'filter_plugins'))
        env.update(environment or {})
        return subprocess.run([sys.executable, '-m', 'ansible.cli.playbook', '-i', 'localhost,',
                               '-c', 'local', str(path / 'main.yml')],
                              capture_output=True, text=True, env=env, check=False)


class InitialRunTests(unittest.TestCase):
    def test_boolean_guard_inspection_is_opt_in_private_and_stops_before_changes(self):
        tasks = yaml.safe_load((ROOT / '01-win-vm-setup.yml').read_text())[0]['tasks']
        boundary = next(index for index, task in enumerate(tasks)
                        if task['name'] == "Require the selected instance's exact owned clone and interfaces")
        inspection = copy.deepcopy(tasks[:boundary])
        include = next(task for task in inspection if 'ansible.builtin.include_tasks' in task)
        include['ansible.builtin.include_tasks'] = str(ROOT / 'tasks/windows_aap_management_network.yml')
        private = 'synthetic-private-value'
        for enabled, have_ssh, valid_selection, expected in [(False, False, True, 0), (True, True, True, 0), (True, False, True, 2), (True, True, False, 2)]:
            with self.subTest(enabled=enabled, have_ssh=have_ssh, valid_selection=valid_selection), tempfile.TemporaryDirectory() as directory:
                changed = Path(directory) / 'unexpected-change'
                variables = {
                    'windows_infrastructure_guard_diagnostics': enabled,
                    'windows_runtime_settings_vault': private,
                    'windows_runtime_hypervisor': {'inventory_host': 'localhost'},
                    'windows_runtime_aap_management': {'configured': True},
                    'windows_runtime_guests': {'example-win': {'role': 'managed', 'version': '2022',
                        'interfaces': [{'network': 'example-isolated', 'mac': '52:54:00:00:00:10'}]}},
                    'vm_name': 'example-win' if valid_selection else private, 'vm_role': 'managed', 'windows_version': '2022',
                    'vm_network': 'example-isolated', 'vm_mac': '52:54:00:00:00:10',
                    'vm_management_network': '', 'vm_management_mac': '',
                    'aap_hactar_source_revision': 'a' * 40, 'hactar_source_public_ip': private,
                }
                environment = {key: private if have_ssh else '' for key in [
                    'AD_AAP_TARGET_SSH_USERNAME', 'AD_AAP_TARGET_SSH_PASSWORD', 'AD_AAP_TARGET_SSH_KNOWN_HOSTS']}
                environment.update(ANSIBLE_LOCAL_TEMP=str(Path(directory) / 'local'),
                                   ANSIBLE_REMOTE_TEMP=str(Path(directory) / 'remote'))
                result = run_play([{'hosts': 'localhost', 'gather_facts': False, 'vars': variables,
                    'tasks': inspection + [{'ansible.builtin.file': {'path': str(changed), 'state': 'touch'}}]}],
                    environment=environment)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, expected, output)
                self.assertEqual(changed.exists(), not enabled)
                self.assertNotIn(private, output)
                if enabled and valid_selection:
                    self.assertIn('primary_mac_matches', output)
                    self.assertIn('existing_ssh_password_present', output)
                else:
                    self.assertNotIn('primary_mac_matches', output)

    def test_existing_copy_requires_the_existing_read_only_source_plan_to_prove_absence(self):
        tasks = yaml.safe_load((ROOT / 'tasks/windows_aap_management_network.yml').read_text())[0]['block']
        operation = next(row for row in tasks if row['name'].startswith('Run the same-job plan'))
        candidate = next(row for row in operation['block'] if row['name'].startswith('Check current registered ownership'))
        plan = candidate['block'][0]
        self.assertEqual(plan['ansible.builtin.include_role']['tasks_from'], 'plan')
        self.assertEqual(plan['vars']['recovery_retire_phase'], 'plan')
        check = candidate['block'][1]
        for record, expected in [({'records_absent': True, 'guest': None}, 0),
                                 ({'records_absent': True, 'guest': {'verified': True}}, 2),
                                 ({'records_absent': False, 'guest': None}, 2)]:
            result = run_play([{'hosts': 'localhost', 'gather_facts': False,
                                'vars': {'recovery_guest_retire_plan': record}, 'tasks': [check]}])
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_queued_network_attempts_stop_after_the_first_completed_transaction(self):
        attempt = yaml.safe_load((ROOT / 'tasks/windows_aap_management_attempt.yml').read_text())
        self.assertEqual(len(attempt), 1)
        self.assertEqual(attempt[0]['when'], 'not windows_aap_network_complete')
        fixture = copy.deepcopy(attempt)
        fixture[0]['block'] = [{'ansible.builtin.set_fact': {
            'example_attempt_count': '{{ example_attempt_count | int + 1 }}',
            'windows_aap_network_complete': True}}]
        include = {'ansible.builtin.include_tasks': 'attempt.yml',
                   'loop': '{{ range(0, 30) | list }}',
                   'when': 'not windows_aap_network_complete'}
        play = [{'hosts': 'localhost', 'gather_facts': False,
                 'vars': {'windows_aap_network_complete': False, 'example_attempt_count': 0},
                 'tasks': [include, {'ansible.builtin.assert': {
                     'that': ['windows_aap_network_complete', 'example_attempt_count | int == 1']}}]}]
        result = run_play(play, {'attempt.yml': fixture})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_infrastructure_failure_shows_only_a_failed_plans_controlled_message(self):
        tasks = yaml.safe_load((ROOT / 'tasks/windows_aap_management_network.yml').read_text())[0]['block']
        operation = next(row for row in tasks if row['name'].startswith('Run the same-job plan'))
        task = next(row for row in operation['rescue'] if row['name'].startswith('Stop after an incomplete'))
        self.assertFalse(task['no_log'])
        for failed in [True, False]:
            plan = {'failed': failed, 'msg': 'Controlled ownership reason' if failed else 'synthetic-private-value',
                    'stderr': 'synthetic-private-value', 'invocation': {'password': 'synthetic-private-value'}}
            result = run_play([{'hosts': 'localhost', 'gather_facts': False,
                                'vars': {'__recovery_release_plan': plan}, 'tasks': [task]}])
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2, output)
            self.assertNotIn('synthetic-private-value', output)
            if failed:
                self.assertIn('Controlled ownership reason', output)

    def test_real_ad_import_preserves_its_network_over_the_common_default(self):
        common = yaml.safe_load((ROOT / '01-win-vm-setup.yml').read_text())[0]
        imported = yaml.safe_load((ROOT / 'create_active_directory_vm.yml').read_text())[1]
        child = {'hosts': 'localhost', 'gather_facts': False,
                 'vars_files': [str(ROOT / 'vars/main.yml')], 'vars': common['vars'],
                 'tasks': [{'ansible.builtin.assert': {
                     'that': ['vm_network == active_directory.libvirt_network',
                              'vm_name == active_directory.hostname',
                              'vm_mac == active_directory.mac']}}]}
        outer = copy.deepcopy(imported)
        outer['ansible.builtin.import_playbook'] = 'child.yml'
        outer['vars']['active_directory'] = {'hostname': 'example-ad',
                                            'libvirt_network': 'example-internal',
                                            'mac': '52:54:00:00:00:01'}
        result = run_play([outer], {'child.yml': [child]})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_ssh_assert_exposes_only_its_fixed_reason_and_retains_validation(self):
        block = yaml.safe_load((ROOT / 'tasks/windows_aap_management_network.yml').read_text())[0]['block']
        task = next(row for row in block if row['name'].startswith('Require existing SSH trust'))
        self.assertFalse(task['no_log'])
        play = [{'hosts': 'localhost', 'gather_facts': False,
                 'vars': {'windows_aap_management': {'route': {
                     'vm_ip': '192.0.2.2', 'aap_hostname': 'https://example.test',
                     'guest_host_keys': ['ssh-ed25519 example']}}}, 'tasks': [task]}]
        for key, expected in [('example', 0), ('synthetic-private-value', 2)]:
            result = run_play(play, environment={'AD_AAP_TARGET_SSH_KNOWN_HOSTS':
                                                 '192.0.2.2 ssh-ed25519 ' + key + '\n'})
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, expected, output)
            self.assertNotIn('synthetic-private-value', output)
            if expected:
                self.assertIn('unregistered selected-guest SSH key', output)
        play[0]['vars']['windows_aap_management']['route']['guest_host_keys'].extend(
            ['ssh-rsa second-example', 'ecdsa-sha2-nistp256 third-example'])
        result = run_play(play, environment={'AD_AAP_TARGET_SSH_KNOWN_HOSTS':
                                             '192.0.2.2 ssh-ed25519 example\n'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for material in ['', 'example.test ssh-ed25519 example\n',
                         '192.0.2.99 ssh-ed25519 example\n',
                         '192.0.2.2 ssh-ed25519 example\n192.0.2.2 ssh-rsa synthetic-private-value\n']:
            result = run_play(play, environment={'AD_AAP_TARGET_SSH_KNOWN_HOSTS': material})
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2, output)
            self.assertNotIn('synthetic-private-value', output)


if __name__ == '__main__':
    unittest.main()
