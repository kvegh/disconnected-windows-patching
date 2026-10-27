# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
"""Exercise production Ansible reboot conditions with Windows operations mocked."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).parents[1]
ACTION = '''
import json, os
from pathlib import Path
from ansible.plugins.action import ActionBase

class ActionModule(ActionBase):
    _requires_connection = False
    def run(self, tmp=None, task_vars=None):
        path = Path(os.environ['APPLICATION_REBOOT_TEST_STATE'])
        state = json.loads(path.read_text())
        args = self._task.args
        result = {'changed': False}
        if args['operation'] == 'ansible.windows.win_reg_stat':
            marker = 'cbs' if 'Component Based Servicing' in args['arguments']['path'] else 'wu'
            result['exists'] = state[marker]
        else:
            assert args['operation'] == 'ansible.windows.win_reboot'
            state['reboots'] += 1
            result['changed'] = True
            if state['clears']:
                state['cbs'] = state['wu'] = False
        path.write_text(json.dumps(state))
        return result
'''


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible is required')
class ApplicationRebootTests(unittest.TestCase):
    def run_flow(self, result=None, cbs=False, wu=False, clears=True):
        with tempfile.TemporaryDirectory(prefix='application-reboot-test-') as temporary:
            directory = Path(temporary)
            plugins = directory / 'collections/ansible_collections/application/test/plugins'
            (plugins / 'action').mkdir(parents=True)
            (plugins / 'modules').mkdir()
            (plugins / 'action/operation.py').write_text(ACTION)
            (plugins / 'modules/operation.py').write_text('# Controller-side mock only.\n')
            production = yaml.safe_load((ROOT / 'tasks/deploy_chocolatey_release.yml').read_text())
            tasks = []
            for original in production:
                if original.get('register') not in ('application_pending_reboots', 'application_reboot_verified') and 'ansible.windows.win_reboot' not in original:
                    continue
                task = dict(original)
                operation = next(key for key in task if key.startswith('ansible.windows.'))
                task['application.test.operation'] = {'operation': operation, 'arguments': task.pop(operation) or {}}
                if 'until' in task:
                    task.update(retries=1, delay=0)
                tasks.append(task)
            self.assertEqual(len(tasks), 3)
            playbook = directory / 'fixture.yml'
            playbook.write_text(yaml.safe_dump([{
                'name': 'Verify reboot completion without remote connections',
                'hosts': 'guest', 'gather_facts': False,
                'vars': {'ansible_connection': 'local', 'ansible_become': False,
                         'installed_applications': {'results': [result or {'rc': 0}]}},
                'tasks': tasks,
            }], sort_keys=False))
            state = directory / 'state.json'
            state.write_text(json.dumps({'cbs': cbs, 'wu': wu, 'clears': clears, 'reboots': 0}))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'tmp'),
                       ANSIBLE_COLLECTIONS_PATH=str(directory / 'collections'),
                       ANSIBLE_NOCOLOR='1', ANSIBLE_DEPRECATION_WARNINGS='true',
                       APPLICATION_REBOOT_TEST_STATE=str(state))
            completed = subprocess.run(['ansible-playbook', '-i', 'guest,', str(playbook)],
                                       cwd=directory, env=env, text=True, capture_output=True, timeout=30)
            output = completed.stdout + completed.stderr
            self.assertNotIn('[DEPRECATION WARNING]', output, output)
            return completed.returncode, json.loads(state.read_text()), output

    def test_clean_host_does_not_reboot(self):
        code, state, output = self.run_flow()
        self.assertEqual(code, 0, output)
        self.assertEqual(state['reboots'], 0)

    def test_installer_reboot_exit_codes_are_honored(self):
        for rc in (1641, 3010):
            with self.subTest(rc=rc):
                code, state, output = self.run_flow(result={'rc': rc})
                self.assertEqual(code, 0, output)
                self.assertEqual(state['reboots'], 1)

    def test_explicit_module_reboot_flag_is_honored(self):
        code, state, output = self.run_flow(result={'rc': 0, 'reboot_required': True})
        self.assertEqual(code, 0, output)
        self.assertEqual(state['reboots'], 1)

    def test_windows_reboot_markers_are_honored_despite_success_exit_code(self):
        for marker in ('cbs', 'wu'):
            with self.subTest(marker=marker):
                code, state, output = self.run_flow(**{marker: True})
                self.assertEqual(code, 0, output)
                self.assertEqual(state['reboots'], 1)
                self.assertFalse(state['cbs'] or state['wu'])

    def test_uncleared_marker_prevents_success(self):
        code, state, output = self.run_flow(cbs=True, clears=False)
        self.assertNotEqual(code, 0, output)
        self.assertEqual(state['reboots'], 1)


if __name__ == '__main__':
    unittest.main()
