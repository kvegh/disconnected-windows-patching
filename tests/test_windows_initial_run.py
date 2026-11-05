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


if __name__ == '__main__':
    unittest.main()
