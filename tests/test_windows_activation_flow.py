# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
"""Exercise real Ansible block/always behavior with all remote operations mocked.

The production task structure/conditions/assertions are retained; only remote
module actions are replaced. No SSH, WinRM, libvirt or systemd calls are made.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml
from jinja2 import Environment, StrictUndefined


ROOT = Path(__file__).parents[1]
REMOTE_ACTIONS = {
    'ansible.builtin.command', 'ansible.builtin.systemd_service',
    'ansible.windows.win_powershell', 'ansible.windows.win_regedit',
    'ansible.windows.win_reg_stat', 'ansible.builtin.wait_for_connection',
}

ACTION = r'''
import json, os
from pathlib import Path
from ansible.plugins.action import ActionBase

class ActionModule(ActionBase):
    _requires_connection = False
    def run(self, tmp=None, task_vars=None):
        args = self._task.args
        path = Path(os.environ['ACTIVATION_TEST_STATE'])
        state = json.loads(path.read_text())
        events = state['events']
        operation = args['operation']
        parameters = args['arguments']
        result = {'changed': False}
        if (operation.endswith('command') or operation.endswith('systemd_service')) and 'windows_runtime_settings_vault' in task_vars:
            assert self._templar.template(task_vars['ansible_connection']) == 'ssh'
            assert self._templar.template(task_vars['ansible_user']) == task_vars['windows_runtime_recovery_pin']['user']
            assert self._templar.template(task_vars['ansible_password']) == ''
            assert self._templar.template(task_vars['ansible_shell_type']) == 'sh'
        if operation == 'verified_release':
            assert state['licensed']
            assert not any(state[key] for key in ('temporary', 'rules', 'network', 'timer'))
            events.append('release')
        elif operation.endswith('win_regedit'):
            events.append(parameters['name'])
            state['policy'][parameters['name']] = parameters['data']
            result['changed'] = True
        elif operation.endswith('win_reg_stat'):
            name = parameters['name']
            result['exists'] = name in state['policy']
            if result['exists']:
                result['value'] = state['policy'][name]
        elif operation.endswith('systemd_service'):
            events.append('stop_timer')
            state['timer'] = False
        elif operation.endswith('command'):
            argv = parameters['argv']
            if argv[0] == 'systemd-run':
                events.append('arm_timer')
                state['timer'] = True
                state['guard_argv'] = argv
            elif 'attach-interface' in argv:
                assert 'NoAutoUpdate' in events and 'DoNotConnectToWindowsUpdateInternetLocations' in events
                if 'guest' in task_vars['groups'].get('windows_managed', []):
                    assert state['policy']['WUServer'].lower().rstrip('/') == task_vars['wsus_internal_url'].lower().rstrip('/')
                    assert state['policy']['WUStatusServer'].lower().rstrip('/') == task_vars['wsus_internal_url'].lower().rstrip('/')
                    assert state['policy']['UseWUServer'] == 1
                assert state['timer']
                events.append('attach')
                state['temporary'] = True
            elif 'detach-interface' in argv:
                events.append('detach')
                state['temporary'] = False
            elif argv[0] == '/bin/sh':
                assert argv[2] == state['guard_argv'][state['guard_argv'].index('-c') + 1]
                if state['failure'] == 'cleanup':
                    result.update(failed=True, msg='Mocked cleanup failure')
                    path.write_text(json.dumps(state))
                    return result
                if state['temporary']:
                    events.append('detach')
                state['temporary'] = False
                state['rules'] = False
                state['network'] = False
                events.append('cleanup')
            elif argv[0] == 'nft':
                if '--check' in argv:
                    events.append('validate_rules')
                else:
                    assert state['timer']
                    events.append('apply_rules')
                    state['rules'] = True
            elif 'net-start' in argv:
                assert state['timer'] and state['rules']
                events.append('start_network')
                state['network'] = True
            elif argv[0] == 'python3':
                snapshot = dict(task_vars['test_baseline'])
                if state['failure'] == 'ownership':
                    snapshot['marker'] = 'foreign-domain'
                if state['temporary']:
                    snapshot['live'] = snapshot['live'] + [{'mac': task_vars['windows_activation_temporary_mac']}]
                result['stdout'] = json.dumps(snapshot)
                events.append('inspect_libvirt')
            elif 'net-info' in argv:
                result.update(stdout='Active: yes', rc=0)
            else:
                raise AssertionError('Unexpected mocked command')
            result.setdefault('rc', 0)
        elif operation.endswith('win_powershell'):
            if task_vars.get('test_ad'):
                assert task_vars['ansible_connection'] == 'local'
                assert task_vars['ansible_user'] == 'example-windows-admin'
                assert task_vars['ansible_password'] == 'example-guest-password'
            mode = parameters['parameters']['Mode']
            events.append(mode)
            if mode == 'Activate' and state['failure'] == 'licensing':
                result.update(failed=True, msg='Mocked activation failure')
            elif mode == 'Activate' and state['failure'] == 'unreachable':
                result.update(unreachable=True, msg='Mocked transient WinRM failure')
            elif mode == 'Verify' and state['failure'] == 'verify':
                result.update(failed=True, msg='Mocked final license/topology failure')
            else:
                if mode == 'Activate':
                    state['licensed'] = True
                result['result'] = {'licensed': state['licensed'], 'grace_minutes': 259200,
                                    'license_status': 1 if state['licensed'] else 5, 'evaluation': True,
                                    'original_topology_verified': not state['temporary'],
                                    'computer_uuid': task_vars['test_baseline'].get('uuid'),
                                    'existing_connected_access': False}
        path.write_text(json.dumps(state))
        return result
'''


def substitute_remote_actions(tasks):
    result = []
    for original in tasks:
        task = dict(original)
        for section in ('block', 'rescue', 'always'):
            if section in task:
                task[section] = substitute_remote_actions(task[section])
        for action in REMOTE_ACTIONS:
            if action in task:
                task['activation.test.operation'] = {
                    'operation': action, 'arguments': task.pop(action),
                }
                # The controller-side mock returns immediately; Windows async
                # process packaging is outside this block/always test.
                task.pop('async', None)
                task.pop('poll', None)
        result.append(task)
    return result


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible is required for control-flow tests')
class ActivationFlowTests(unittest.TestCase):
    def test_normal_and_deadline_cleanup_scripts_parse_for_both_paths(self):
        tasks = yaml.safe_load((ROOT / 'tasks/activate_windows_evaluation.yml').read_text())
        script = next(task['ansible.builtin.set_fact']['windows_activation_cleanup_script']
                      for task in tasks if 'windows_activation_cleanup_script' in task.get('ansible.builtin.set_fact', {}))
        for selected in (False, True):
            with self.subTest(selected=selected):
                variables = {'windows_runtime_settings_vault': 'mock ciphertext'} if selected else {}
                rendered = Environment(undefined=StrictUndefined).from_string(script).render(**variables)
                result = subprocess.run(['/bin/sh', '-n'], input=rendered, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                if selected:
                    self.assertLess(rendered.index('domif-setlink'), rendered.index('/usr/sbin/nft'))

    def run_flow(self, failure='', licensed=False, connected=False, managed=True, source=None, approved_connected=None, selected=False,
                 complete=False, ad=False, full_guarded=False):
        with tempfile.TemporaryDirectory(prefix='windows-activation-flow-') as temporary:
            directory = Path(temporary)
            actions = directory / 'collections/ansible_collections/activation/test/plugins/action'
            actions.mkdir(parents=True)
            (actions / 'operation.py').write_text(ACTION)
            modules = actions.parent / 'modules'
            modules.mkdir()
            (modules / 'operation.py').write_text('# Controller-side mock action only.\n')
            (directory / 'assets').symlink_to(ROOT / 'assets', target_is_directory=True)
            tasks_dir = directory / 'tasks'
            tasks_dir.mkdir()
            production = yaml.safe_load((ROOT / 'tasks/activate_windows_evaluation.yml').read_text())
            (tasks_dir / 'activate_windows_evaluation.yml').write_text(yaml.safe_dump(substitute_remote_actions(production), sort_keys=False))
            guarded = yaml.safe_load((ROOT / 'tasks/activate_windows_guest.yml').read_text())
            (tasks_dir / 'activate_windows_guest.yml').write_text(yaml.safe_dump(substitute_remote_actions(guarded), sort_keys=False))
            main = yaml.safe_load((ROOT / 'activate_windows_evaluations.yml').read_text())
            guarded_tasks = next(task['block'] for task in guarded if task['name'] == 'Inspect activate and verify the same exact guest')
            include = next(task for task in guarded_tasks if task.get('ansible.builtin.include_tasks') == 'tasks/activate_windows_evaluation.yml')
            completion = []
            if complete:
                # Keep the actual completion gate and first release-input guard.
                # Remote provenance/publication has its own existing tests.
                release_guard = yaml.safe_load((ROOT / 'tasks/windows_verified_guest_release.yml').read_text())[0]
                for task in guarded_tasks[guarded_tasks.index(include) + 1:] + main[1]['tasks'][1:]:
                    if task.get('ansible.builtin.include_tasks') == 'tasks/windows_verified_guest_release.yml':
                        completion.extend([release_guard, {'name': 'Observe the verified release boundary',
                                                          'activation.test.operation': {'operation': 'verified_release', 'arguments': {}}}])
                    elif 'ansible.builtin.debug' not in task:
                        completion.extend(substitute_remote_actions([task]))
            baseline = {'live': [{'mac': '52:54:00:11:22:33'}], 'persistent': [{'mac': '52:54:00:11:22:33'}]}
            if selected:
                baseline.update(uuid='00000000-0000-0000-0000-000000000001', all_macs=['52:54:00:11:22:33'],
                                activation_network={'active': False, 'bridge': 'virbr-example', 'gateway': '192.0.2.1'})
            fixture = [{
                'name': 'Exercise activation cleanup without remote connections',
                'hosts': 'guest', 'gather_facts': False,
                'vars': {
                    'ansible_connection': 'local', 'ansible_become': False,
                    'windows_activation_settings': {'vm_name': 'example-clone', 'windows_version': '2025'},
                    'windows_activation_hypervisor': 'hypervisor',
                    'windows_activation_connected_network': 'example-activation',
                    'wsus_internal_url': 'https://updates.internal.example:8531',
                    'windows_activation_before': {'result': {'licensed': licensed, 'existing_connected_access': connected}},
                    'windows_activation_domain_before': {'stdout': json.dumps(baseline)},
                    'test_baseline': baseline,
                },
                'tasks': [include, *completion],
            }]
            if selected:
                fixture[0]['vars'].update(windows_runtime_settings_vault='mock ciphertext',
                                          windows_runtime_hypervisor={'machine_id': '0' * 32},
                                          windows_runtime_recovery_pin={'machine_id': '0' * 32, 'address': '192.0.2.1',
                                                                        'user': 'example', 'port': 22},
                                          windows_activation_hypervisor_trust={'path': '/tmp/example-pinned-trust'})
            if complete:
                pin = {'machine_id': '0' * 32, 'address': '192.0.2.1', 'port': 22, 'user': 'example'}
                fixture[0]['vars'].update(ansible_connection='winrm', ansible_port=5986,
                                          ansible_winrm_scheme='https', ansible_winrm_transport='ntlm',
                                          ansible_winrm_server_cert_validation='ignore',
                                          windows_runtime_hypervisor=pin, windows_runtime_recovery_pin=pin,
                                          windows_runtime_guests={'guest': {}}, windows_hostname='guest',
                                          active_directory={'hostname': 'example-ad'})
            if ad:
                baseline.update(name='guest', marker='aap-disconnected-windows-clone', running=True,
                                hypervisor_machine_id='0' * 32, title='example-instance:guest',
                                disks=['/opt/vms/win-guest-clone.disk.qcow2'])
                baseline['live'] = baseline['persistent'] = [
                    {'mac': '52:54:00:11:22:33', 'type': 'network', 'source': {'network': 'example-isolated'}, 'link': 'up'}]
                baseline['activation_network'].update(forward='nat', ipv6=False, domain_references=[])
                pin = {'machine_id': '0' * 32, 'address': '192.0.2.1', 'port': 22,
                       'known_hosts': '192.0.2.1 ssh-ed25519 example'}
                fixture[0]['vars'].update(
                    test_ad=True, ansible_user='example-windows-admin', ansible_password='example-guest-password',
                    windows_activation_approved=True, windows_activation_network='example-activation',
                    windows_runtime_expected_instance='example-instance', windows_runtime_hypervisor=pin,
                    windows_runtime_recovery_pin={**pin, 'user': 'example', 'isolation_bridges': ['virbr-example']},
                    windows_runtime_guests={'guest': {'role': 'ad', 'version': '2025', 'interfaces': [
                        {'mac': '52:54:00:11:22:33', 'address': '192.0.2.10', 'network': 'example-isolated'}]}},
                    active_directory={'hostname': 'guest', 'mac': '52:54:00:11:22:33', 'ipv4': '192.0.2.10',
                                      'prefix_length': 24, 'gateway': '192.0.2.1', 'libvirt_network': 'example-isolated'},
                    ad_windows_prerequisites={'result': {'LicenseStatus': 1 if licensed else 5,
                                                        'Evaluation': True, 'GraceMinutes': 259200 if licensed else 0}})
                ad_tasks = yaml.safe_load((ROOT / 'prepare_active_directory_guest.yml').read_text())[0]['tasks']
                start = next(i for i, task in enumerate(ad_tasks) if task['name'].startswith('Retain the current license evidence'))
                end = next(i for i, task in enumerate(ad_tasks) if task['name'].startswith('Require a valid installed Windows license'))
                fixture[0]['tasks'] = ad_tasks[start:end + 1] + [{
                    'name': 'Preserve the actual initial prerequisite evidence',
                    'ansible.builtin.assert': {'that': [
                        'ad_windows_prerequisites.result.LicenseStatus == ' + ('1' if licensed else '5')]}}]
            approved_connected = connected if approved_connected is None else approved_connected
            fixture[0]['vars']['windows_activation_settings']['libvirt_interfaces'] = [
                {'mac': '52:54:00:11:22:33', 'network': 'example-activation' if approved_connected else 'example-isolated'}]
            if full_guarded:
                baseline.update(name='example-clone', uuid='00000000-0000-0000-0000-000000000001',
                                marker='aap-disconnected-windows-clone', running=True)
                baseline['live'] = baseline['persistent'] = [{
                    'mac': '52:54:00:11:22:33', 'type': 'network',
                    'source': {'network': 'example-isolated'}, 'link': 'up'}]
                fixture[0]['vars']['windows_activation_settings']['interfaces'] = [{'mac': '52:54:00:11:22:33'}]
                fixture[0]['vars']['windows_activation_approved'] = True
                fixture[0]['tasks'] = [{'ansible.builtin.include_tasks': 'tasks/activate_windows_guest.yml'}]
            playbook = directory / 'fixture.yml'
            playbook.write_text(yaml.safe_dump(fixture, sort_keys=False))
            inventory = directory / 'inventory.yml'
            guest_variables = {key: fixture[0]['vars'][key]
                               for key in ('windows_runtime_recovery_pin', 'windows_activation_hypervisor_trust')
                               if key in fixture[0]['vars']}
            inventory.write_text(yaml.safe_dump({'all': {
                'hosts': {'guest': guest_variables, 'hypervisor': {'ansible_connection': 'local'}},
                'children': {'windows_managed': {'hosts': {'guest': {}} if managed else {}}}}}))
            statefile = directory / 'state.json'
            policy = {} if source is None else {'WUServer': source, 'WUStatusServer': source}
            statefile.write_text(json.dumps({'events': [], 'temporary': False, 'timer': False,
                                            'rules': False, 'network': False,
                                            'licensed': licensed, 'failure': failure, 'policy': policy}))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'tmp'),
                       ANSIBLE_COLLECTIONS_PATH=str(directory / 'collections'),
                       ANSIBLE_NOCOLOR='1', ANSIBLE_RETRY_FILES_ENABLED='false',
                       ANSIBLE_DEPRECATION_WARNINGS='true', ACTIVATION_TEST_STATE=str(statefile))
            process = subprocess.run(['ansible-playbook', '-i', str(inventory), str(playbook)],
                                     cwd=directory, env=env, capture_output=True, text=True, timeout=45)
            state = json.loads(statefile.read_text())
            output = process.stdout + process.stderr
            self.assertNotIn('[DEPRECATION WARNING]', output, output)
            return process.returncode, state, output

    def assert_restored(self, state):
        self.assertFalse(state['temporary'])
        self.assertFalse(state['timer'])
        self.assertIn('NoAutoUpdate', state['events'])
        self.assertIn('DoNotConnectToWindowsUpdateInternetLocations', state['events'])
        self.assertLess(state['events'].index('detach'), state['events'].index('stop_timer'))
        self.assertIn('Inspect', state['events'])
        guard = state['guard_argv']
        self.assertTrue(any('domif-setlink' in value and 'detach-interface' in value for value in guard))
        self.assertNotIn('--config', guard)

    def test_success_restores_topology_and_disarms_deadline(self):
        code, state, output = self.run_flow()
        self.assertEqual(code, 0, output)
        self.assertTrue(state['licensed'])
        self.assert_restored(state)

    def test_licensing_error_still_detaches_and_stops_deployment(self):
        code, state, output = self.run_flow(failure='licensing')
        self.assertNotEqual(code, 0, output)
        self.assert_restored(state)

    def test_winrm_unreachable_still_detaches_immediately(self):
        code, state, output = self.run_flow(failure='unreachable')
        self.assertNotEqual(code, 0, output)
        self.assert_restored(state)

    def test_licensed_clone_never_changes_policy_connectivity_or_license(self):
        code, state, output = self.run_flow(licensed=True)
        self.assertEqual(code, 0, output)
        self.assertEqual(state['events'], [])

    def test_existing_repository_connection_does_not_add_or_remove_nics(self):
        code, state, output = self.run_flow(connected=True, managed=False)
        self.assertEqual(code, 0, output)
        self.assertNotIn('attach', state['events'])
        self.assertNotIn('detach', state['events'])
        self.assertNotIn('arm_timer', state['events'])
        self.assertIn('Inspect', state['events'])

    def test_fresh_managed_clone_gets_internal_source_before_exposure(self):
        code, state, output = self.run_flow()
        self.assertEqual(code, 0, output)
        for name in ('WUServer', 'WUStatusServer', 'UseWUServer'):
            self.assertLess(state['events'].index(name), state['events'].index('attach'))

    def test_conflicting_managed_source_fails_before_any_write_or_connectivity(self):
        code, state, output = self.run_flow(source='https://conflicting.example:8531')
        self.assertNotEqual(code, 0, output)
        self.assertEqual(state['events'], [])
        self.assertFalse(state['temporary'])

    def test_matching_managed_source_is_preserved(self):
        source = 'HTTPS://UPDATES.internal.example:8531/'
        code, state, output = self.run_flow(source=source)
        self.assertEqual(code, 0, output)
        self.assertEqual(state['policy']['WUServer'], source)
        self.assertNotIn('WUServer', state['events'])

    def test_default_route_without_approved_connected_adapter_still_needs_temporary_nic(self):
        code, state, output = self.run_flow(connected=True, approved_connected=False)
        self.assertEqual(code, 0, output)
        self.assertIn('attach', state['events'])
        self.assert_restored(state)

    def test_selected_activation_arms_before_rules_and_cleans_network_before_timer(self):
        code, state, output = self.run_flow(selected=True)
        self.assertEqual(code, 0, output)
        self.assert_restored(state)
        self.assertFalse(state['rules'])
        self.assertFalse(state['network'])
        for first, second in [('arm_timer', 'apply_rules'), ('apply_rules', 'start_network'),
                              ('start_network', 'attach'), ('cleanup', 'stop_timer')]:
            self.assertLess(state['events'].index(first), state['events'].index(second))

    def test_selected_license_failure_removes_its_rules_and_network(self):
        code, state, output = self.run_flow(selected=True, failure='licensing')
        self.assertNotEqual(code, 0, output)
        self.assert_restored(state)
        self.assertFalse(state['rules'])
        self.assertFalse(state['network'])

    def test_completed_activation_releases_only_after_cleanup_and_final_verification(self):
        code, state, output = self.run_flow(selected=True, complete=True)
        self.assertEqual(code, 0, output)
        self.assertLess(state['events'].index('stop_timer'), state['events'].index('Verify'))
        self.assertLess(state['events'].index('Verify'), state['events'].index('release'))

    def test_licensed_skip_still_verifies_and_releases_without_activation_changes(self):
        code, state, output = self.run_flow(selected=True, complete=True, licensed=True)
        self.assertEqual(code, 0, output)
        self.assertEqual(state['events'], ['Verify', 'release'])

    def test_licensing_cleanup_or_final_verification_failure_never_releases(self):
        for failure in ('licensing', 'cleanup', 'verify'):
            with self.subTest(failure=failure):
                code, state, output = self.run_flow(selected=True, complete=True, failure=failure)
                self.assertNotEqual(code, 0, output)
                self.assertNotIn('release', state['events'])

    def test_ad_invalid_evaluation_uses_complete_guards_and_preserves_initial_evidence(self):
        code, state, output = self.run_flow(selected=True, managed=False, ad=True)
        self.assertEqual(code, 0, output)
        self.assertTrue(state['licensed'])
        self.assertLess(state['events'].index('inspect_libvirt'), state['events'].index('arm_timer'))
        self.assertLess(state['events'].index('stop_timer'), state['events'].index('Verify'))
        self.assertNotIn('release', state['events'])

    def test_licensed_ad_keeps_existing_path_without_pre_promotion_topology_checks(self):
        code, state, output = self.run_flow(selected=True, managed=False, ad=True, licensed=True)
        self.assertEqual(code, 0, output)
        self.assertEqual(state['events'], [])

    def test_ad_activation_failure_keeps_license_gate_closed_and_cleans_exact_resources(self):
        code, state, output = self.run_flow(selected=True, managed=False, ad=True, failure='licensing')
        self.assertNotEqual(code, 0, output)
        self.assert_restored(state)
        self.assertFalse(state['rules'])
        self.assertFalse(state['network'])

    def test_complete_legacy_path_retains_its_native_evidence_and_connection_context(self):
        code, state, output = self.run_flow(full_guarded=True)
        self.assertEqual(code, 0, output)
        self.assert_restored(state)
        self.assertIn('Verify', state['events'])

    def test_ad_foreign_native_marker_stops_before_policy_or_temporary_network_writes(self):
        code, state, output = self.run_flow(selected=True, managed=False, ad=True, failure='ownership')
        self.assertNotEqual(code, 0, output)
        self.assertEqual(state['events'], ['Inspect', 'inspect_libvirt'])
        self.assertFalse(state['temporary'])
        self.assertFalse(state['rules'])
        self.assertFalse(state['timer'])


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible is required for inventory preflight tests')
class ActivationInventoryTests(unittest.TestCase):
    def test_activation_connection_preserves_existing_guest_baseline_variables(self):
        with tempfile.TemporaryDirectory(prefix='windows-activation-host-binding-') as temporary:
            directory = Path(temporary)
            production = yaml.safe_load((ROOT / 'activate_windows_evaluations.yml').read_text())[0]
            add_host = next(task for task in production['tasks'] if 'ansible.builtin.add_host' in task)
            nic = {'mac': '52:54:00:11:22:33', 'ipv4_address': '192.0.2.10'}
            inventory = {'all': {'hosts': {'hypervisor': {'ansible_connection': 'local'},
                                           'example-guest': {'windows_hostname': 'example-guest',
                                                             'windows_connection_address': '192.0.2.10',
                                                             'windows_network_interfaces': [nic]}}}}
            play = [{'name': 'Bind the existing guest without a remote connection',
                     'hosts': 'hypervisor', 'gather_facts': False,
                     'vars': {'windows_activation_username': 'example-login',
                              'windows_activation_password': 'example-secret',
                              'windows_activation_network': 'example-network',
                              'windows_activation_targets': [{'inventory_host': 'example-guest',
                                                              'connection': {'address': '192.0.2.10', 'port': 5986,
                                                                             'scheme': 'https', 'transport': 'ntlm',
                                                                             'server_cert_validation': 'ignore'}}]},
                     'tasks': [add_host]},
                    {'name': 'Check that activation retains baseline inputs for fresh provenance',
                     'hosts': 'windows_activation_guests', 'gather_facts': False,
                     'tasks': [{'name': 'Require preserved baseline identity and network settings',
                                'ansible.builtin.assert': {'that': ["windows_hostname == 'example-guest'",
                                                                  "windows_connection_address == '192.0.2.10'",
                                                                  'windows_network_interfaces == expected_nics',
                                                                  "windows_activation_hypervisor == 'hypervisor'"]},
                                'vars': {'expected_nics': [nic]}, 'no_log': True}]}]
            (directory / 'inventory.yml').write_text(yaml.safe_dump(inventory))
            (directory / 'fixture.yml').write_text(yaml.safe_dump(play))
            result = subprocess.run(['ansible-playbook', '-i', str(directory / 'inventory.yml'),
                                     str(directory / 'fixture.yml')], cwd=directory, text=True,
                                    capture_output=True, timeout=20,
                                    env=dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'tmp')))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def run_preflight(self, inventory, approved=True):
        with tempfile.TemporaryDirectory(prefix='windows-activation-inventory-') as temporary:
            directory = Path(temporary)
            production = yaml.safe_load((ROOT / 'activate_windows_evaluations.yml').read_text())[0]
            play = {
                'name': 'Validate the resolved hypervisor target without remote operations',
                'hosts': production['hosts'], 'gather_facts': False,
                'vars': {
                    'windows_activation_approved': approved,
                    'windows_activation_network': 'example-activation',
                    'windows_activation_username': 'example-login',
                    'windows_activation_password': 'example-secret',
                    'windows_activation_targets': [{'inventory_host': 'example-guest', 'vm_name': 'example-clone'}],
                },
                'tasks': [production['tasks'][0]],
            }
            playbook = directory / 'preflight.yml'
            playbook.write_text(yaml.safe_dump([play]))
            inventory_file = directory / 'inventory.yml'
            inventory_file.write_text(yaml.safe_dump(inventory))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'tmp'),
                       ANSIBLE_NOCOLOR='1', ANSIBLE_DEPRECATION_WARNINGS='true')
            result = subprocess.run(['ansible-playbook', '-i', str(inventory_file), str(playbook)],
                                    cwd=directory, env=env, capture_output=True, text=True, timeout=20)
            output = result.stdout + result.stderr
            self.assertNotIn('[DEPRECATION WARNING]', output, output)
            return result.returncode, output

    def test_host_alias_does_not_require_a_same_named_inventory_group(self):
        code, output = self.run_preflight({'all': {'hosts': {'hypervisor': {}}}})
        self.assertEqual(code, 0, output)

    def test_group_resolving_to_multiple_hypervisors_is_rejected(self):
        code, output = self.run_preflight({'all': {'children': {'hypervisor': {'hosts': {'example-first': {}, 'example-second': {}}}}}})
        self.assertNotEqual(code, 0, output)

    def test_single_host_still_requires_explicit_activation_approval(self):
        code, output = self.run_preflight({'all': {'hosts': {'hypervisor': {}}}}, approved=False)
        self.assertNotEqual(code, 0, output)


if __name__ == '__main__':
    unittest.main()
