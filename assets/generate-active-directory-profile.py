"""Create the initial private AD profile for the Ansible initialization playbook."""

import base64
import datetime
import importlib.util
import json
from pathlib import Path
import secrets
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def main():
    seed = json.load(sys.stdin)
    spec = importlib.util.spec_from_file_location('ad_model', Path(__file__).with_name('active-directory-model.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile = dict(seed)
    profile.update(module.model(seed['prefix'], seed['dns_domain']))
    profile['domain_admin_username'] = seed['netbios'] + '\\Administrator'
    for key in ('domain_admin_password', 'dsrm_password', 'bind_password',
                'ca_key_password', 'certificate_password'):
        profile[key] = secrets.token_urlsafe(36) + 'aA1!'
    profile['bind_username'] = seed['prefix'].lower() + '-ldap'
    profile['bind_dn'] = 'CN=' + profile['bind_username'] + ',' + profile['root_dn']
    profile['mock_passwords'] = {item['key']: secrets.token_urlsafe(30) + 'aA1!'
                                 for item in profile['resource_sets']}
    password_suffix = profile.pop('demo_user_password_suffix', None)
    if password_suffix is not None:
        if not isinstance(password_suffix, str) or not password_suffix:
            raise ValueError('The protected demo password suffix must be a nonempty string.')
        if profile.get('allow_simple_demo_passwords') is not True:
            raise ValueError('Password derivation requires the explicitly selected scoped demo policy.')
    for user in profile['users']:
        if len(user['username']) > 20:
            raise ValueError('Choose a shorter prefix for SAM account names.')
        user['password'] = (user['username'] + password_suffix if password_suffix is not None
                            else secrets.token_urlsafe(30) + 'aA1!')
        user['email'] = user['username'] + '@' + seed['dns_domain']
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, seed['prefix'] + ' Demo CA')])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - datetime.timedelta(minutes=10))
          .not_valid_after(now + datetime.timedelta(days=1825))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False,
                         content_commitment=False, data_encipherment=False,
                         key_agreement=False, key_cert_sign=True, crl_sign=True,
                         encipher_only=False, decipher_only=False), critical=True)
          .sign(ca_key, hashes.SHA256()))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fqdn = seed['hostname'] + '.' + seed['dns_domain']
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, fqdn)])
    leaf = (x509.CertificateBuilder().subject_name(leaf_name).issuer_name(ca.subject)
            .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=10))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(fqdn)]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True,
                           content_commitment=False, data_encipherment=False,
                           key_agreement=False, key_cert_sign=False, crl_sign=False,
                           encipher_only=False, decipher_only=False), critical=True)
            .sign(ca_key, hashes.SHA256()))
    profile['fqdn'] = fqdn
    profile['ca_certificate'] = ca.public_bytes(serialization.Encoding.PEM).decode()
    profile['ca_private_key_encrypted'] = ca_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(profile['ca_key_password'].encode())).decode()
    profile['certificate_pfx_base64'] = base64.b64encode(pkcs12.serialize_key_and_certificates(
        fqdn.encode(), leaf_key, leaf, [ca],
        serialization.BestAvailableEncryption(profile['certificate_password'].encode()))).decode()
    profile['certificate_thumbprint'] = leaf.fingerprint(hashes.SHA1()).hex().upper()
    print(json.dumps(profile))


if __name__ == '__main__':
    main()
