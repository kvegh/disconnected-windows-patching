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


ROOT = Path(__file__).parents[1]
REMOTE_ACTIONS = {
    'ansible.builtin.command', 'ansible.builtin.systemd_service',
    'ansible.windows.win_powershell', 'ansible.windows.win_regedit',
    'ansible.windows.win_reg_stat',
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
        if operation.endswith('win_regedit'):
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
            elif argv[0] == 'python3':
                snapshot = dict(task_vars['test_baseline'])
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
            mode = parameters['parameters']['Mode']
            events.append(mode)
            if mode == 'Activate' and state['failure'] == 'licensing':
                result.update(failed=True, msg='Mocked activation failure')
            elif mode == 'Activate' and state['failure'] == 'unreachable':
                result.update(unreachable=True, msg='Mocked transient WinRM failure')
            else:
                if mode == 'Activate':
                    state['licensed'] = True
                result['result'] = {'licensed': state['licensed'], 'grace_minutes': 259200,
                                    'original_topology_verified': not state['temporary']}
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
    def run_flow(self, failure='', licensed=False, connected=False, managed=True, source=None, approved_connected=None):
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
            main = yaml.safe_load((ROOT / 'activate_windows_evaluations.yml').read_text())
            include = next(task for task in main[1]['tasks'] if 'ansible.builtin.include_tasks' in task)
            baseline = {'live': [{'mac': '52:54:00:11:22:33'}], 'persistent': [{'mac': '52:54:00:11:22:33'}]}
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
                'tasks': [include],
            }]
            approved_connected = connected if approved_connected is None else approved_connected
            fixture[0]['vars']['windows_activation_settings']['libvirt_interfaces'] = [
                {'mac': '52:54:00:11:22:33', 'network': 'example-activation' if approved_connected else 'example-isolated'}]
            playbook = directory / 'fixture.yml'
            playbook.write_text(yaml.safe_dump(fixture, sort_keys=False))
            inventory = directory / 'inventory.yml'
            inventory.write_text(yaml.safe_dump({'all': {
                'hosts': {'guest': {}, 'hypervisor': {'ansible_connection': 'local'}},
                'children': {'windows_managed': {'hosts': {'guest': {}} if managed else {}}}}}))
            statefile = directory / 'state.json'
            policy = {} if source is None else {'WUServer': source, 'WUStatusServer': source}
            statefile.write_text(json.dumps({'events': [], 'temporary': False, 'timer': False,
                                            'licensed': licensed, 'failure': failure, 'policy': policy}))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'tmp'),
                       ANSIBLE_COLLECTIONS_PATH=str(directory / 'collections'),
                       ANSIBLE_NOCOLOR='1', ANSIBLE_RETRY_FILES_ENABLED='false',
                       ANSIBLE_DEPRECATION_WARNINGS='false', ACTIVATION_TEST_STATE=str(statefile))
            process = subprocess.run(['ansible-playbook', '-i', str(inventory), str(playbook)],
                                     cwd=directory, env=env, capture_output=True, text=True, timeout=45)
            state = json.loads(statefile.read_text())
            return process.returncode, state, process.stdout + process.stderr

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


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible is required for inventory preflight tests')
class ActivationInventoryTests(unittest.TestCase):
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
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'tmp'), ANSIBLE_NOCOLOR='1')
            result = subprocess.run(['ansible-playbook', '-i', str(inventory_file), str(playbook)],
                                    cwd=directory, env=env, capture_output=True, text=True, timeout=20)
            return result.returncode, result.stdout + result.stderr

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
