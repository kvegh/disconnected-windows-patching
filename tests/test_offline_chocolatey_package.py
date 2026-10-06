"""Verify offline package contents, reproducibility, and binary upload integrity."""
import email
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'assets/build-offline-chocolatey-package.py'
spec = importlib.util.spec_from_file_location('offline_package', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OfflinePackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.binary = bytes(range(256)) * 100 + b'\r\n\x00\xff\n\r'
        self.installer = self.directory / 'vendor-x64.exe'
        self.installer.write_bytes(self.binary)
        self.package = {
            'id': 'demo.install', 'version': '1.2.3', 'title': 'Demo',
            'vendor_version': '1.2.3', 'project_url': 'https://example.invalid/',
            'release_url': 'https://example.invalid/release',
            'installer_filename': self.installer.name,
            'installer_url': 'https://example.invalid/vendor-x64.exe',
            'installer_sha256': hashlib.sha256(self.binary).hexdigest(),
            'installer_type': 'exe', 'silent_arguments': '/S',
        }

    def test_archive_embeds_verified_installer_and_offline_hook(self):
        artifact = module.build(self.package, self.directory)
        with zipfile.ZipFile(artifact['package']) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('tools/vendor-x64.exe'), self.binary)
            hook = archive.read('tools/chocolateyInstall.ps1').decode()
            self.assertIn('Get-FileHash', hook)
            self.assertIn('Install-ChocolateyInstallPackage', hook)
            self.assertNotIn('https://', hook)
            root = ET.fromstring(archive.read('demo.install.nuspec'))
            namespace = {'n': 'http://schemas.microsoft.com/packaging/2015/06/nuspec.xsd'}
            self.assertEqual(root.find('n:metadata/n:version', namespace).text, '1.2.3')
            relationships = ET.fromstring(archive.read('_rels/.rels'))
            self.assertEqual(relationships[0].attrib['Target'], '/demo.install.nuspec')
            ET.fromstring(archive.read('[Content_Types].xml'))

    def test_rebuild_is_identical_despite_installer_timestamp_change(self):
        first = module.build(self.package, self.directory)
        self.assertTrue(first['changed'])
        os.utime(self.installer, (123456789, 123456789))
        second = module.build(self.package, self.directory)
        self.assertFalse(second['changed'])
        self.assertEqual(first['sha256'], second['sha256'])

    def test_multipart_preserves_all_package_bytes(self):
        artifact = module.build(self.package, self.directory)
        message = email.message_from_bytes(
            ('Content-Type: multipart/form-data; boundary=' + artifact['boundary'] + '\r\n\r\n').encode()
            + Path(artifact['multipart']).read_bytes())
        part = message.get_payload()[0]
        self.assertEqual(part.get_param('name', header='Content-Disposition'), 'nuget.asset')
        self.assertEqual(part.get_payload(decode=True), Path(artifact['package']).read_bytes())

    def test_checksum_mismatch_refuses_package_creation(self):
        self.installer.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            module.build(self.package, self.directory)
        self.assertEqual(list(self.directory.glob('*.nupkg')), [])

    def test_path_traversal_is_rejected(self):
        self.package['installer_filename'] = '../vendor.exe'
        with self.assertRaisesRegex(ValueError, 'Invalid manifest field'):
            module.build(self.package, self.directory)


if __name__ == '__main__':
    unittest.main()
