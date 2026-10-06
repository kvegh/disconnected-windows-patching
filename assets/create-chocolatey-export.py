#!/usr/bin/env python3
"""Create a deterministic selected-package export, never a Nexus database dump."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
import importlib.util
_spec = importlib.util.spec_from_file_location("offline_package", Path(__file__).with_name("build-offline-chocolatey-package.py"))
_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_builder)
digest, entry, install_script, replace_if_changed = (_builder.digest, _builder.entry, _builder.install_script, _builder.replace_if_changed)


def export(selection, directory):
    directory = Path(directory)
    packages = []
    seen = set()
    for package in selection['packages']:
        name = package['id'] + '.' + package['version'] + '.nupkg'
        if name in seen or package['track'] not in ['baseline', 'current']:
            raise ValueError('Duplicate package or invalid release track')
        seen.add(name)
        artifact = next(a for a in selection['artifacts'] if Path(a['package']).name == name)
        source = directory / name
        if digest(source) != artifact['sha256']:
            raise ValueError('Export package differs from synchronized artifact')
        with zipfile.ZipFile(source) as archive:
            if hashlib.sha256(archive.read('tools/' + package['installer_filename'])).hexdigest() != package['installer_sha256']:
                raise ValueError('Embedded installer is not the pinned vendor release')
            if archive.read('tools/chocolateyInstall.ps1') != install_script(package):
                raise ValueError('Package installation hook differs from the maintained offline hook')
        packages.append({key: package[key] for key in ['id', 'version', 'track', 'vendor_version', 'installer_sha256']})
        packages[-1].update(filename=name, sha256=artifact['sha256'])
    manifest = json.dumps({'schema': 1, 'packages': packages}, sort_keys=True, separators=(',', ':')).encode()
    manifest_hash = hashlib.sha256(manifest).hexdigest()
    descriptor, temporary_name = tempfile.mkstemp(dir=directory, suffix='.export.zip.tmp')
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(entry('manifest.json'), manifest)
            for package in sorted(packages, key=lambda p: p['filename']):
                with archive.open(entry('packages/' + package['filename']), 'w', force_zip64=True) as output:
                    with (directory / package['filename']).open('rb') as source:
                        shutil.copyfileobj(source, output)
        checksum = digest(temporary)
        target = directory / (checksum + '.zip')
        changed = replace_if_changed(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'archive': str(target), 'sha256': checksum, 'manifest_sha256': manifest_hash,
            'package_count': len(packages), 'changed': changed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    print(json.dumps(export(json.load(sys.stdin), args.directory)))
