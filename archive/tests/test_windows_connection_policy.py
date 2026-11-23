"""Render the actual encrypted loader with both existing WinRM policies offline."""

from copy import deepcopy
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

from ansible.parsing.vault import VaultLib, VaultSecret
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import yaml

from test_windows_runtime import profile


ROOT = Path(__file__).resolve().parents[1]


def public_certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic fixture CA')])
    now = datetime.datetime.now(datetime.timezone.utc)
    return (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode())


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Native Ansible is required.')
class WindowsConnectionPolicyTests(unittest.TestCase):
    def render(self, validation, ca=False):
        document = deepcopy(profile())
        settings = document['windows_runtime']['settings']
        settings.pop('windows_runtime_winrm_ready')
        if ca:
            settings['windows_runtime_winrm_ca'] = public_certificate()
        vault = VaultLib([('default', VaultSecret(b'synthetic-fixture-only'))])
        ciphertext = vault.encrypt(yaml.safe_dump(document).encode()).decode()
        with tempfile.TemporaryDirectory(prefix='windows-connection-policy-') as temporary:
            directory = Path(temporary)
            (directory / 'vault-password').write_text('synthetic-fixture-only')
            variables = {'windows_runtime_settings_vault': ciphertext,
                         'windows_runtime_expected_instance': 'example-instance'}
            inventory = {'all': {'hosts': {'localhost': {'ansible_connection': 'local',
                                                        'ansible_python_interpreter': sys.executable}},
                                 'children': {'windows_managed': {'hosts': {'example-ext': {
                                     'ansible_connection': 'winrm', 'ansible_port': 5986,
                                     'ansible_winrm_scheme': 'https', 'ansible_winrm_transport': 'ntlm',
                                     'ansible_winrm_server_cert_validation': validation}}}}}}
            (directory / 'inventory.yml').write_text(yaml.safe_dump(inventory))
            (directory / 'variables.yml').write_text(yaml.safe_dump(variables))
            play = [{'name': 'Render the existing encrypted Windows loader without remote execution',
                     'hosts': 'windows_managed', 'gather_facts': False,
                     'tasks': [{'name': 'Exercise the actual production loader',
                                'ansible.builtin.include_tasks': str(ROOT / 'tasks/windows_runtime_settings.yml')},
                               {'name': 'Require the selected policy without an inspection readiness flag',
                                'ansible.builtin.assert': {'that': [
                                    "'windows_runtime_winrm_ready' not in windows_runtime_selected",
                                    "ansible_winrm_server_cert_validation != 'validate' or windows_runtime_ca_file.path is defined",
                                    "ansible_winrm_server_cert_validation != 'ignore' or windows_runtime_ca_file.path is not defined"]}},
                               {'name': 'Record native rendering acceptance',
                                'ansible.builtin.debug': {'msg': 'NATIVE_WINDOWS_CONNECTION_ACCEPTED'}},
                               {'name': 'Remove the synthetic public CA file after the native check',
                                'ansible.builtin.file': {'path': '{{ windows_runtime_ca_file.path }}', 'state': 'absent'},
                                'delegate_to': 'localhost', 'vars': {'ansible_connection': 'local'},
                                'when': 'windows_runtime_ca_file.path is defined'}]}]
            (directory / 'play.yml').write_text(yaml.safe_dump(play))
            environment = dict(os.environ, ANSIBLE_HOME=str(directory / 'home'),
                               ANSIBLE_LOCAL_TEMP=str(directory / 'local'),
                               ANSIBLE_REMOTE_TEMP=str(directory / 'remote'),
                               ANSIBLE_FILTER_PLUGINS=str(ROOT / 'filter_plugins'),
                               ANSIBLE_NOCOLOR='1')
            return subprocess.run(['ansible-playbook', '-i', str(directory / 'inventory.yml'),
                                   '--vault-password-file', str(directory / 'vault-password'),
                                   '-e', '@' + str(directory / 'variables.yml'), str(directory / 'play.yml')],
                                  env=environment, text=True, capture_output=True, timeout=60)

    def test_lab_ignore_without_ca_or_readiness_flag_uses_the_actual_loader(self):
        result = self.render('ignore')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NATIVE_WINDOWS_CONNECTION_ACCEPTED', result.stdout)

    def test_validate_without_ca_refuses_before_guest_execution(self):
        result = self.render('validate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Require the selected Windows HTTPS connection policy', result.stdout)
        self.assertNotIn('NATIVE_WINDOWS_CONNECTION_ACCEPTED', result.stdout)

    def test_validate_with_public_ca_retains_the_existing_strict_path(self):
        result = self.render('validate', ca=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NATIVE_WINDOWS_CONNECTION_ACCEPTED', result.stdout)


if __name__ == '__main__':
    unittest.main()
