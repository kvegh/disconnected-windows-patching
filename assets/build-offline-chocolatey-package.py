#!/usr/bin/env python3
"""Build deterministic offline NuGet packages from verified vendor installers.

No network calls or credentials. Input is one public manifest entry on stdin.
The accompanying raw multipart body lets Ansible uri upload binary files without
base64 conversion by older ansible-core multipart implementations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def quoted(value):
    return "'" + value.replace("'", "''") + "'"


def install_script(package):
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$installer = Join-Path $PSScriptRoot " + quoted(package['installer_filename']),
        "if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne "
        + quoted(package['installer_sha256']) + ") { throw 'Embedded installer checksum mismatch.' }",
        "if (-not [Environment]::Is64BitOperatingSystem) { throw 'This package requires 64-bit Windows.' }",
        "$arguments = @{",
        "    PackageName = $env:ChocolateyPackageName",
        "    FileType = " + quoted(package['installer_type']),
        "    SilentArgs = " + quoted(package['silent_arguments']),
        "    File = $installer",
        "    ValidExitCodes = @(0, 1641, 3010)",
        "}",
        "Install-ChocolateyInstallPackage @arguments", "",
    ]).encode('utf-8')


def nuspec(package):
    root = ET.Element('package', xmlns='http://schemas.microsoft.com/packaging/2015/06/nuspec.xsd')
    metadata = ET.SubElement(root, 'metadata')
    values = {
        'id': package['id'], 'version': package['version'], 'title': package['title'],
        'authors': 'AAP demo package maintainers', 'projectUrl': package['project_url'],
        'requireLicenseAcceptance': 'false',
        'description': 'Self-contained offline demo package for ' + package['title']
        + ' ' + package['vendor_version'] + '. Vendor installer and license notices are embedded.',
        'tags': 'offline demo x64',
    }
    for key, value in values.items():
        ET.SubElement(metadata, key).text = str(value)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def entry(name):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def replace_if_changed(temporary, target):
    if target.is_symlink():
        raise ValueError('Refusing to replace a symlink')
    if target.exists() and digest(temporary) == digest(target):
        temporary.unlink()
        return False
    os.replace(temporary, target)
    return True


def build(package, directory):
    for key, expression in {
        'id': r'[a-z0-9][a-z0-9.-]*',
        'version': r'\d+\.\d+\.\d+(?:\.\d+)?',
        'installer_filename': r'[A-Za-z0-9][A-Za-z0-9._-]*\.(?:exe|msi)',
        'installer_sha256': r'[a-f0-9]{64}',
        'installer_type': r'(?:exe|msi)',
    }.items():
        if not re.fullmatch(expression, str(package.get(key, ''))):
            raise ValueError('Invalid manifest field: ' + key)
    directory = Path(directory)
    installer = directory / package['installer_filename']
    if installer.is_symlink() or digest(installer) != package['installer_sha256']:
        raise ValueError('Installer missing or checksum mismatch')
    target = directory / (package['id'] + '.' + package['version'] + '.nupkg')
    manifest_name = package['id'] + '.nuspec'
    relationships = ET.Element('Relationships', xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
    ET.SubElement(relationships, 'Relationship', Id='manifest', Target='/' + manifest_name,
                  Type='http://schemas.microsoft.com/packaging/2010/07/manifest')
    types = ET.Element('Types', xmlns='http://schemas.openxmlformats.org/package/2006/content-types')
    for extension in ['nuspec', 'ps1', 'exe', 'msi', 'txt']:
        ET.SubElement(types, 'Default', Extension=extension, ContentType='application/octet-stream')
    ET.SubElement(types, 'Default', Extension='rels', ContentType='application/vnd.openxmlformats-package.relationships+xml')
    descriptor, temporary_name = tempfile.mkstemp(dir=directory, suffix='.nupkg.tmp')
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            contents = {
                manifest_name: nuspec(package),
                '[Content_Types].xml': ET.tostring(types, encoding='utf-8', xml_declaration=True),
                '_rels/.rels': ET.tostring(relationships, encoding='utf-8', xml_declaration=True),
                'tools/chocolateyInstall.ps1': install_script(package),
                'tools/VERIFICATION.txt': (package['installer_url'] + '\nSHA256: '
                                          + package['installer_sha256'] + '\nRelease: '
                                          + package['release_url'] + '\n').encode(),
            }
            for name, content in sorted(contents.items()):
                archive.writestr(entry(name), content)
            with archive.open(entry('tools/' + installer.name), 'w', force_zip64=True) as output:
                with installer.open('rb') as source:
                    shutil.copyfileobj(source, output)
        changed = replace_if_changed(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    checksum = digest(target)
    boundary = 'AAP' + checksum
    multipart = target.with_suffix('.multipart')
    descriptor, temporary_name = tempfile.mkstemp(dir=directory, suffix='.multipart.tmp')
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open('wb') as output:
            output.write(('--' + boundary + '\r\nContent-Disposition: form-data; name="nuget.asset"; filename="'
                          + target.name + '"\r\nContent-Type: application/octet-stream\r\n\r\n').encode('ascii'))
            with target.open('rb') as source:
                shutil.copyfileobj(source, output)
            output.write(('\r\n--' + boundary + '--\r\n').encode('ascii'))
        changed = replace_if_changed(temporary, multipart) or changed
    finally:
        temporary.unlink(missing_ok=True)
    return {'id': package['id'], 'version': package['version'], 'changed': changed, 'package': str(target), 'sha256': checksum,
            'multipart': str(multipart), 'boundary': boundary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    print(json.dumps(build(json.load(sys.stdin), args.directory)))
