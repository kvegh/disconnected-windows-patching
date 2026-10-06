"""Verify export integrity and reproducibility independently of Nexus availability."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('chocolatey_export', ROOT / 'assets/create-chocolatey-export.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        binary = bytes(range(256)) * 100
        (self.directory / 'vendor.exe').write_bytes(binary)
        self.packages = []
        self.artifacts = []
        for version, track in [('1.2.3', 'baseline'), ('1.2.4', 'current')]:
            package = {
                'id': 'demo.install', 'version': version, 'track': track,
                'title': 'Demo', 'vendor_version': version,
                'installer_filename': 'vendor.exe', 'installer_type': 'exe',
                'silent_arguments': '/S', 'installer_sha256': hashlib.sha256(binary).hexdigest(),
                'installer_url': 'https://example.invalid/vendor.exe',
                'project_url': 'https://example.invalid/', 'release_url': 'https://example.invalid/release',
            }
            self.packages.append(package)
            self.artifacts.append(module._builder.build(package, self.directory))
        self.selection = {'packages': self.packages, 'artifacts': self.artifacts}

    def test_export_contains_only_the_manifest_and_selected_packages(self):
        artifact = module.export(self.selection, self.directory)
        with zipfile.ZipFile(artifact['archive']) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json', 'packages/demo.install.1.2.3.nupkg', 'packages/demo.install.1.2.4.nupkg'})
            manifest_bytes = archive.read('manifest.json')
            self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), artifact['manifest_sha256'])
            manifest = json.loads(manifest_bytes)
            self.assertEqual([p['track'] for p in manifest['packages']], ['baseline', 'current'])
            for package in manifest['packages']:
                self.assertEqual(hashlib.sha256(archive.read('packages/' + package['filename'])).hexdigest(), package['sha256'])
        self.assertEqual(module.digest(Path(artifact['archive'])), artifact['sha256'])

    def test_repeat_export_is_identical_and_reports_no_change(self):
        first = module.export(self.selection, self.directory)
        second = module.export(self.selection, self.directory)
        self.assertTrue(first['changed'])
        self.assertFalse(second['changed'])
        self.assertEqual(first['sha256'], second['sha256'])

    def test_changed_synchronized_package_is_rejected(self):
        Path(self.artifacts[0]['package']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'differs from synchronized'):
            module.export(self.selection, self.directory)

    def test_modified_install_hook_is_rejected_even_with_updated_package_hash(self):
        path = Path(self.artifacts[0]['package'])
        with zipfile.ZipFile(path) as original:
            contents = {name: original.read(name) for name in original.namelist()}
        contents['tools/chocolateyInstall.ps1'] = b'Invoke-WebRequest https://example.invalid/'
        with zipfile.ZipFile(path, 'w') as replacement:
            for name, data in contents.items():
                replacement.writestr(name, data)
        self.artifacts[0]['sha256'] = module.digest(path)
        with self.assertRaisesRegex(ValueError, 'installation hook differs'):
            module.export(self.selection, self.directory)


if __name__ == '__main__':
    unittest.main()
