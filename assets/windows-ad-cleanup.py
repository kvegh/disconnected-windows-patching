# Purpose: [rationale](../docs/supporting-code.md#active-directory-and-aap-verification).
"""Read a small, exact deletion plan for this dedicated regional demo.

Only Ansible's existing platform/controller modules perform deletion.
"""

import importlib.util
import json
from pathlib import Path
import ssl
import sys
import tempfile
import urllib.error
from urllib.parse import urlencode


def load(filename):
    spec = importlib.util.spec_from_file_location(filename.replace('-', '_'), Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = load('inspect-aap-ad-migration.py')
verification = load('verify-aap-ad-regions.py')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def snapshot(p, api):
    verification.validate_profile(p)
    prefix = p['prefix']
    plan = {'prefix': prefix, 'organization': [], 'job_templates': [], 'projects': [],
            'inventories': [], 'credentials': [], 'teams': [], 'users': [], 'role_definitions': []}
    authenticators = api.listing('/api/gateway/v1/authenticators/?' + urlencode({'name': prefix + ' Active Directory'}))
    require(len(authenticators) <= 1 and all(row.get('name') == prefix + ' Active Directory'
            and row.get('type') == migration.LDAP_TYPE for row in authenticators), 'Unexpected demo authenticator.')
    require(p.get('saved') is None or not authenticators,
            'Remove LDAP maps and authenticator before regional resources.')
    definitions = api.listing('/api/gateway/v1/role_definitions/?page_size=200')
    definitions_by_id = {str(row['id']): row for row in definitions}
    orgs = api.listing('/api/gateway/v1/organizations/?' + urlencode({'name': prefix + ' Regional Identity Demo'}))
    require(len(orgs) <= 1 and all(row.get('name') == prefix + ' Regional Identity Demo' for row in orgs),
            'The dedicated demo organization is not unique.')
    if orgs:
        org = str(orgs[0]['id'])
        plan['organization'] = [{'id': orgs[0]['id'], 'name': orgs[0]['name']}]
        for endpoint, allowed in (
                ('projects', set(verification.RESOURCE_SETS)),
                ('inventories', {key + ' Inventory' for key in verification.RESOURCE_SETS}),
                ('credentials', {key + ' Credential' for key in verification.RESOURCE_SETS}),
                ('job_templates', {key + ' ' + label for key in verification.RESOURCE_SETS
                                   for label in verification.OPERATIONS.values()}),
                ('teams', {prefix + ' ' + scope + ' ' + role for scope in verification.ACCESS_LABELS.values()
                           for role in verification.ROLES})):
            rows = migration.owned_listing(api, endpoint, org, allowed, endpoint, gateway=endpoint == 'teams')
            for row in rows:
                if endpoint == 'projects':
                    require(row.get('scm_type') == 'git' and row.get('scm_url') == verification.SOURCE_URL
                            and row.get('scm_branch') == 'main', 'An owned mock project changed source.')
                if endpoint == 'job_templates':
                    require(row.get('playbook') == 'mock_regional_job.yml', 'An owned template changed playbook.')
            plan[endpoint] = rows
        owned_objects = {('awx.' + kind, str(row['id'])) for kind, endpoint in verification.ENDPOINTS.items()
                         for row in plan[endpoint]}
        for template in plan['job_templates']:
            key = template['name'].split(' ', 1)[0]
            project = [row for row in plan['projects'] if row['name'] == key]
            inventory = [row for row in plan['inventories'] if row['name'] == key + ' Inventory']
            credential = [row for row in plan['credentials'] if row['name'] == key + ' Credential']
            attached = api.listing('/api/controller/v2/job_templates/' + str(template['id']) + '/credentials/')
            require(len(project) == len(inventory) == len(credential) == len(attached) == 1
                    and str(template['project']) == str(project[0]['id'])
                    and str(template['inventory']) == str(inventory[0]['id'])
                    and str(attached[0]['id']) == str(credential[0]['id']), 'A mock template references unrelated resources.')
        for team in plan['teams']:
            grants = api.listing('/api/gateway/v1/role_team_assignments/?team=' + str(team['id']))
            require(all((definitions_by_id.get(str(grant['role_definition']), {}).get('content_type'),
                         str(grant['object_id'])) in owned_objects for grant in grants),
                    'A demo team has grants to unrelated objects.')
            members = api.listing('/api/gateway/v1/teams/' + str(team['id']) + '/users/')
            require(all(row.get('username') in {user['username'] for user in p['users']} for row in members),
                    'A demo team contains unrelated users.')
    else:
        org = None
    for user in p['users'] + p['retired_users']:
        rows = api.listing('/api/gateway/v1/users/?' + urlencode({'username': user['username']}))
        require(len(rows) <= 1 and all(row.get('username') == user['username'] for row in rows),
                'A demo username is not unique.')
        for row in rows:
            require(row.get('is_superuser') is False and row.get('is_platform_auditor') is False
                    and row.get('is_system_auditor', False) is False, 'A demo identity has protected platform privileges.')
            associations = row.get('associated_authenticators', {})
            if authenticators:
                require(isinstance(associations, dict) and set(associations) == {str(authenticators[0]['id'])},
                        'A demo user is not owned exclusively by the selected LDAP authenticator.')
            for endpoint, allowed in (('teams', {str(team['id']) for team in plan['teams']}),
                                      ('organizations', {org} if org else set())):
                memberships = api.listing('/api/gateway/v1/users/' + str(row['id']) + '/' + endpoint + '/')
                require(all(str(value['id']) in allowed for value in memberships),
                        'A demo identity belongs to unrelated organizations or teams.')
            require(not api.listing('/api/gateway/v1/role_user_assignments/?user=' + str(row['id'])),
                    'A demo identity has direct grants outside its LDAP team model.')
            plan['users'].append({'id': row['id'], 'username': row['username']})
    for row in definitions:
        for kind in verification.ENDPOINTS:
            if row.get('name') == prefix + ' ' + kind + ' Reader':
                require(row.get('content_type') == 'awx.' + kind
                        and row.get('permissions') == ['awx.view_' + kind], 'A dedicated reader role changed permissions.')
                grants = []
                for endpoint in ('role_team_assignments', 'role_user_assignments'):
                    grants += api.listing('/api/gateway/v1/' + endpoint + '/?role_definition=' + str(row['id']))
                own_ids = {str(item['id']) for item in plan[verification.ENDPOINTS[kind]]}
                require(all(str(grant['object_id']) in own_ids for grant in grants),
                        'A dedicated reader role is used outside the demo.')
                plan['role_definitions'].append({key: row[key] for key in ('id', 'name', 'content_type', 'permissions')})
    # Keep only immutable identifiers and the resource links used by the fixed model.
    for endpoint in ('projects', 'inventories', 'credentials', 'job_templates', 'teams'):
        plan[endpoint] = [{key: row[key] for key in ('id', 'name', 'organization', 'project', 'inventory',
                                                   'playbook', 'scm_type', 'scm_url', 'scm_branch') if key in row}
                          for row in plan[endpoint]]
    return plan


def remaining(current, saved, before):
    """A retry may remove fewer remaining objects, never claim a new one."""
    require(current.get('prefix') == saved.get('prefix') == before.get('prefix'), 'The saved AD scope changed.')
    for kind in current.keys() - {'prefix'}:
        expected = {str(row['id']): row for row in saved[kind]}
        original = {str(row['id']) for row in before[kind]}
        for row in current[kind]:
            require(str(row['id']) in expected and row == expected[str(row['id'])],
                    'A regional object changed identity after the cleanup preview.')
            require(str(row['id']) not in original, 'A regional object predates this test deployment.')
    return current


def main():
    p = json.load(sys.stdin)
    with tempfile.TemporaryDirectory(prefix='windows-ad-cleanup-') as directory:
        ca = Path(directory) / 'ca.pem'
        ca.write_text(p['ca']); ca.chmod(0o600)
        result = snapshot(p, migration.API(p, ca))
        if p.get('saved') is not None:
            result = remaining(result, p['saved'], p['before'])
        print(json.dumps(result))


def failure_reason(error):
    """Expose a bounded failure category without API credentials or transport details."""
    if isinstance(error, AssertionError):
        return str(error)
    cause = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(cause, ssl.SSLCertVerificationError):
        return 'The selected AAP API certificate failed validation.'
    return 'Protected regional cleanup inspection failed (' + type(cause).__name__ + ').'


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'reason': failure_reason(error)}))
        raise SystemExit(1)
