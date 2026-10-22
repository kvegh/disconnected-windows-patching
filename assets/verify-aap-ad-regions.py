"""Verify regional AAP grants and, optionally, real LDAP login permissions."""

import base64
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

LABELS = {'DK': 'Denmark', 'NO': 'Norway', 'EU': 'EU', 'NZ': 'New Zealand'}


def verify(p):
    with tempfile.TemporaryDirectory(prefix='ad-rbac-verification-') as directory:
        ca = Path(directory) / 'ca.pem'
        ca.write_text(p['ca'])
        ca.chmod(0o600)
        context = ssl.create_default_context(cafile=str(ca))
        base = p['url'].rstrip('/')

        def request(path, user=None, method='GET', body=None):
            user = user or {'username': p['admin_username'], 'password': p['admin_password']}
            authorization = base64.b64encode((user['username'] + ':' + user['password']).encode()).decode()
            req = urllib.request.Request(base + path, method=method,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Authorization': 'Basic ' + authorization,
                                                  'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, context=context, timeout=30) as response:
                    payload = response.read()
                    return response.status, json.loads(payload) if payload else {}
            except urllib.error.HTTPError as error:
                return error.code, {}

        def get(path, user=None):
            status, data = request(path, user)
            if status != 200:
                raise AssertionError('A required verification read failed: HTTP ' + str(status))
            if data.get('next'):
                raise AssertionError('Verification unexpectedly requires pagination.')
            return data

        prefix = p['prefix']
        orgs = get('/api/gateway/v1/organizations/?name=' + urllib.parse.quote(prefix + ' Regional Identity Demo'))['results']
        if len(orgs) != 1:
            raise AssertionError('The expected regional organization is not unique.')
        org = str(orgs[0]['id'])
        teams = get('/api/gateway/v1/teams/?organization=' + org + '&page_size=200')['results']
        definitions = {x['id']: x for x in get('/api/gateway/v1/role_definitions/?page_size=200')['results']}
        endpoints = {'inventory': 'inventories', 'credential': 'credentials', 'jobtemplate': 'job_templates'}
        resources = {}
        for kind, endpoint in endpoints.items():
            data = get('/api/controller/v2/' + endpoint + '/?organization=' + org + '&page_size=200')['results']
            if len(data) != (8 if kind == 'jobtemplate' else 4):
                raise AssertionError('Unexpected regional resource count.')
            resources[kind] = {x['name']: x for x in data}
        if len(teams) != 12:
            raise AssertionError('Unexpected regional team count.')
        grants_checked = 0
        for region, label in LABELS.items():
            expected = {
                ('awx.inventory', str(resources['inventory'][prefix + ' ' + label + ' Mock Inventory']['id'])),
                ('awx.credential', str(resources['credential'][prefix + ' ' + label + ' Mock Credential']['id'])),
                ('awx.jobtemplate', str(resources['jobtemplate'][prefix + ' ' + label + ' read']['id'])),
                ('awx.jobtemplate', str(resources['jobtemplate'][prefix + ' ' + label + ' simulate_change']['id'])),
            }
            for level in ('reader', 'executor', 'admin'):
                team = next(x for x in teams if x['name'] == prefix + ' ' + label + ' ' + level)
                grants = get('/api/gateway/v1/role_team_assignments/?team=' + str(team['id']) + '&page_size=200')['results']
                if len(grants) != 4:
                    raise AssertionError('Unexpected number of resource grants for a regional team.')
                actual = set()
                for grant in grants:
                    role = definitions[grant['role_definition']]
                    actual.add((role['content_type'], str(grant['object_id'])))
                    if level == 'reader' and (not role['name'].endswith(' Reader') or
                                              any(not permission.startswith('awx.view_') for permission in role['permissions'])):
                        raise AssertionError('A reader has a permission beyond resource viewing.')
                    if level == 'executor' and role['name'] not in ('Inventory Use', 'Credential Use', 'JobTemplate Execute'):
                        raise AssertionError('An executor has an unexpected role.')
                    if level == 'admin' and not role['name'].endswith(' Admin'):
                        raise AssertionError('A regional administrator has an unexpected role.')
                if actual != expected:
                    raise AssertionError('A team has a cross-region resource grant.')
                grants_checked += len(grants)
        for template in resources['jobtemplate'].values():
            if any(template.get(key) for key in ('ask_inventory_on_launch', 'ask_credential_on_launch', 'ask_variables_on_launch')):
                raise AssertionError('A mock job permits replacing its fixed regional inputs.')
        summary = {'regions_verified': 4, 'teams_verified': 12,
                   'object_scoped_grants_verified': grants_checked,
                   'cross_region_grants': 0, 'reader_roles_are_view_only': True,
                   'ldap_logins_verified': 0, 'permission_checks': 0, 'mock_jobs_verified': 0}
        jobs = []
        if p.get('verify_logins'):
            for user in p['users']:
                principal = get('/api/gateway/v1/me/', user)['results'][0]
                if principal['username'].lower() != user['username'].lower() or principal.get('is_superuser'):
                    raise AssertionError('Unexpected identity or superuser status after LDAP login.')
                allowed = {user['region']} | ({'EU'} if user['region'] in ('DK', 'NO') else set())
                user_access_deadline = time.monotonic() + 60
                for region, label in LABELS.items():
                    for kind, endpoint in endpoints.items():
                        suffix = {'inventory': 'Mock Inventory', 'credential': 'Mock Credential', 'jobtemplate': 'read'}[kind]
                        resource = resources[kind][prefix + ' ' + label + ' ' + suffix]
                        path = '/api/controller/v2/' + endpoint + '/' + str(resource['id']) + '/'
                        status, visible = request(path, user)
                        if region in allowed:
                            while status in (403, 404) and time.monotonic() < user_access_deadline:
                                time.sleep(2)
                                status, visible = request(path, user)
                            if status != 200:
                                raise AssertionError('Expected access did not converge: '
                                                     + user['region'] + '/' + user['role'] + ' -> '
                                                     + region + '/' + kind + ' HTTP ' + str(status))
                            patch_status, _ = request(path, user, 'PATCH', {'description': visible.get('description', '')})
                            if user['role'] == 'admin' and patch_status != 200:
                                raise AssertionError('A regional administrator cannot administer its resource.')
                            if user['role'] != 'admin' and patch_status not in (403, 404):
                                raise AssertionError('A reader or executor can modify resource configuration.')
                        elif status not in (403, 404):
                            raise AssertionError('A cross-region resource is visible.')
                        summary['permission_checks'] += 1
                    template = resources['jobtemplate'][prefix + ' ' + label + ' read']
                    status, launch = request('/api/controller/v2/job_templates/' + str(template['id']) + '/launch/', user, 'POST', {})
                    permitted = region in allowed and user['role'] in ('executor', 'admin')
                    if permitted:
                        if status not in (200, 201, 202) or not (launch.get('job') or launch.get('id')):
                            raise AssertionError('A permitted mock execution failed to launch.')
                        jobs.append(launch.get('job') or launch['id'])
                    elif status not in (403, 404):
                        raise AssertionError('A reader or cross-region identity can execute a mock job.')
                    summary['permission_checks'] += 1
                summary['ldap_logins_verified'] += 1
            deadline = time.monotonic() + 1200
            while jobs:
                remaining = []
                for job in jobs:
                    state = get('/api/controller/v2/jobs/' + str(job) + '/')['status']
                    if state in ('failed', 'error', 'canceled'):
                        raise AssertionError('An authorized inert mock job did not complete successfully.')
                    if state == 'successful':
                        summary['mock_jobs_verified'] += 1
                    else:
                        remaining.append(job)
                jobs = remaining
                if jobs and time.monotonic() > deadline:
                    raise AssertionError('Authorized mock jobs exceeded the verification deadline.')
                if jobs:
                    time.sleep(10)
        return summary


if __name__ == '__main__':
    try:
        print(json.dumps(verify(json.load(sys.stdin))))
    except Exception as error:
        print(json.dumps({'verified': False, 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Protected verification failed.'}))
        raise SystemExit(1)
