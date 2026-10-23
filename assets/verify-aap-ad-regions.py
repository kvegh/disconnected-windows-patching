"""Independently verify country-owned AAP resources and real LDAP permissions."""

import base64
import json
from pathlib import Path
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROLES = ('reader', 'executor', 'admin')
ACTOR_ACCESS = {'DK': {'DK', 'EU'}, 'NO': {'NO', 'EU'},
                'NZ': {'NZ'}, 'HU': {'EU'}}
ACCESS_LABELS = {'DK': 'DKlocal', 'NO': 'NOlocal',
                 'EU': 'EUapproved', 'NZ': 'NZlocal'}
RESOURCE_SETS = {'DKlocal': ('DK', 'DK'), 'NOlocal': ('NO', 'NO'),
                 'DKEUapproved': ('DK', 'EU'), 'NOEUapproved': ('NO', 'EU'),
                 'NZlocal': ('NZ', 'NZ')}
ENDPOINTS = {'inventory': 'inventories', 'credential': 'credentials',
             'project': 'projects', 'jobtemplate': 'job_templates'}
OPERATIONS = {'read': 'Read', 'simulate_change': 'Simulate Change'}
SOURCE_URL = 'https://github.com/kvegh/disconnected-windows-patching.git'
DENIED = (403, 404)


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def validate_profile(p):
    """Compare the profile with an independent, fixed acceptance matrix."""
    prefix = p['prefix']
    require(isinstance(prefix, str) and bool(prefix), 'The identity prefix is missing.')
    supplied = p['resource_sets']
    require(len(supplied) == 5 and
            {item['key']: (item['owner'], item['access']) for item in supplied} == RESOURCE_SETS,
            'The protected resource-set model differs from the accepted matrix.')
    users = p['users']
    expected = {(country, role, '{}-{}-{}'.format(prefix.lower(), country.lower(), role))
                for country in ACTOR_ACCESS for role in ROLES}
    actual = {(user['region'], user['role'], user['username']) for user in users}
    require(len(users) == 12 and actual == expected,
            'The protected identities differ from the twelve accepted actors.')
    if p.get('verify_logins'):
        require(all(isinstance(user.get('password'), str) and user['password'] for user in users),
                'An LDAP verification identity has no protected password.')
    retired = p['retired_users']
    require(len(retired) == 3 and {user['username'] for user in retired} ==
            {prefix.lower() + '-eu-' + role for role in ROLES},
            'The retired EU-only identity list is incomplete.')


def expected_name(key, kind, operation='read'):
    return key if kind == 'project' else key + ' ' + (
        OPERATIONS[operation] if kind == 'jobtemplate' else kind.title())


def decode_variables(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            raise AssertionError('Mock variables are not a fixed JSON mapping.') from None
    require(isinstance(value, dict), 'Mock variables are not a fixed mapping.')
    return value


def verify_with_request(p, request):
    """Use an injected transport so acceptance and failure paths can be tested offline."""
    validate_profile(p)
    prefix = p['prefix']

    def get(path, user=None):
        status, data = request(path, user)
        require(status == 200, 'A required verification read failed: HTTP ' + str(status))
        return data

    def listing(path, user=None):
        data = get(path, user)
        require(not data.get('next'), 'Verification unexpectedly requires pagination.')
        require(isinstance(data.get('results'), list), 'A required API list is missing.')
        return data['results']

    def by_name(rows, expected, label):
        require(len(rows) == len(expected) and {row['name'] for row in rows} == set(expected),
                'Unexpected ' + label + ' names or count.')
        require(len({str(row['id']) for row in rows}) == len(rows),
                'Unexpected duplicate ' + label + ' identifiers.')
        return {row['name']: row for row in rows}

    orgs = listing('/api/gateway/v1/organizations/?name=' + urllib.parse.quote(
        prefix + ' Regional Identity Demo'))
    require(len(orgs) == 1, 'The expected regional organization is not unique.')
    org = str(orgs[0]['id'])
    suffix = '?organization=' + org + '&page_size=200'
    team_names = {prefix + ' ' + label + ' ' + role
                  for label in ACCESS_LABELS.values() for role in ROLES}
    teams = by_name(listing('/api/gateway/v1/teams/' + suffix), team_names, 'access team')
    definitions = {str(row['id']): row for row in listing(
        '/api/gateway/v1/role_definitions/?page_size=200')}
    resources = {}
    for kind, endpoint in ENDPOINTS.items():
        names = {expected_name(key, kind, operation)
                 for key in RESOURCE_SETS
                 for operation in (OPERATIONS if kind == 'jobtemplate' else ('read',))}
        resources[kind] = by_name(listing('/api/controller/v2/' + endpoint + '/' + suffix),
                                  names, kind)

    def resource(key, kind, operation='read'):
        return resources[kind][expected_name(key, kind, operation)]

    grants_checked = 0
    for access, label in ACCESS_LABELS.items():
        keys = [key for key, (_, scope) in RESOURCE_SETS.items() if scope == access]
        for role in ROLES:
            team = teams[prefix + ' ' + label + ' ' + role]
            grants = listing('/api/gateway/v1/role_team_assignments/?team=' +
                             str(team['id']) + '&page_size=200')
            expected = set()
            for key in keys:
                for kind in ENDPOINTS:
                    for operation in (OPERATIONS if kind == 'jobtemplate' else ('read',)):
                        if role == 'reader' or (role == 'executor' and kind == 'project'):
                            role_name = prefix + ' ' + kind + ' Reader'
                        else:
                            type_name = {'jobtemplate': 'JobTemplate'}.get(kind, kind.title())
                            action = 'Admin' if role == 'admin' else (
                                'Execute' if kind == 'jobtemplate' else 'Use')
                            role_name = type_name + ' ' + action
                        expected.add(('awx.' + kind, str(resource(key, kind, operation)['id']),
                                      role_name))
            actual = set()
            for grant in grants:
                definition = definitions.get(str(grant['role_definition']))
                require(definition is not None, 'A scoped grant refers to an unknown role.')
                require(str(grant['team']) == str(team['id']),
                        'A team grant was returned for a different team.')
                kind = definition['content_type'].removeprefix('awx.')
                if role == 'reader' or (role == 'executor' and kind == 'project'):
                    require(definition['permissions'] == ['awx.view_' + kind],
                            'A reader or executor Project grant exceeds view-only access.')
                actual.add((definition['content_type'], str(grant['object_id']), definition['name']))
            require(len(grants) == len(expected) and actual == expected,
                    'A team has missing, extra or incorrectly privileged resource grants.')
            grants_checked += len(grants)
    require(grants_checked == 75, 'The scoped grant total differs from the accepted matrix.')

    # Check snapshots before any job can be launched, including the second operation.
    machine_types = listing('/api/controller/v2/credential_types/?name=Machine&kind=ssh&page_size=200')
    require(len(machine_types) == 1 and machine_types[0]['name'] == 'Machine' and
            machine_types[0].get('kind') == 'ssh', 'The synthetic Machine credential type is not unique.')
    for key, (owner, access) in RESOURCE_SETS.items():
        project = resource(key, 'project')
        require(project.get('scm_type') == 'git' and project.get('scm_url') == SOURCE_URL and
                project.get('scm_branch') == 'main' and not project.get('scm_update_on_launch'),
                'A mock Project differs from the fixed public demo source.')
        hosts = listing('/api/controller/v2/inventories/' + str(resource(key, 'inventory')['id']) +
                        '/hosts/?page_size=200')
        require(len(hosts) == 1 and hosts[0]['name'] == 'localhost' and hosts[0].get('enabled') is True,
                'A mock inventory does not contain exactly one enabled localhost.')
        require(decode_variables(resource(key, 'inventory').get('variables')).get('ansible_connection') == 'local'
                and decode_variables(hosts[0].get('variables')).get('ansible_connection') == 'local',
                'A mock inventory or host does not explicitly use a local connection.')
        credential = resource(key, 'credential')
        require(str(credential.get('credential_type')) == str(machine_types[0]['id']) and
                credential.get('inputs', {}).get('username') == prefix + '-mock-' + key.lower() and
                bool(credential.get('inputs', {}).get('password')) and
                set(credential.get('inputs', {})) == {'username', 'password'},
                'A mock credential differs from its independent synthetic Machine definition.')
        for operation in OPERATIONS:
            template = resource(key, 'jobtemplate', operation)
            require(template.get('playbook') == 'mock_regional_job.yml' and
                    template.get('job_type') == 'run' and
                    str(template.get('inventory')) == str(resource(key, 'inventory')['id']) and
                    str(template.get('project')) == str(project['id']),
                    'A mock job does not use its fixed local inventory, Project and playbook.')
            require(not template.get('survey_enabled') and not any(
                value for name, value in template.items() if name.startswith('ask_') and
                name.endswith('_on_launch')),
                'A mock job permits replacing its fixed launch inputs.')
            require(decode_variables(template.get('extra_vars')) == {
                'demo_resource_set': key, 'demo_owner': owner, 'demo_access': access,
                'demo_operation': operation}, 'A mock job has incorrect fixed ownership or clearance.')
            credentials = listing('/api/controller/v2/job_templates/' + str(template['id']) +
                                  '/credentials/?page_size=200')
            require(len(credentials) == 1 and str(credentials[0]['id']) ==
                    str(resource(key, 'credential')['id']),
                    'A mock job does not use exactly its own synthetic credential.')

    for retired in p['retired_users']:
        query = '?username=' + urllib.parse.quote(retired['username']) + '&page_size=200'
        for service in ('gateway/v1', 'controller/v2'):
            require(not listing('/api/' + service + '/users/' + query),
                    'A retired EU-only identity remains in AAP.')

    summary = {'actor_countries_verified': 4, 'resource_sets_verified': 5,
               'projects_verified': 5, 'inventories_verified': 5, 'credentials_verified': 5,
               'job_templates_verified': 10, 'teams_verified': 12,
               'object_scoped_grants_verified': grants_checked, 'cross_region_grants': 0,
               'reader_roles_are_view_only': True, 'retired_users_absent': 3,
               'ldap_logins_verified': 0, 'permission_checks': 0,
               'description_patch_checks': 0, 'resource_list_checks': 0,
               'team_membership_checks': 0, 'mock_jobs_verified': 0,
               'localhost_execution_verified': 0}
    jobs = {}

    def wait_for_allowed(path, user, deadline):
        status, data = request(path, user)
        while status in DENIED and time.monotonic() < deadline:
            time.sleep(2)
            status, data = request(path, user)
        return status, data

    def check_teams(service, identity, expected, deadline=None):
        path = '/api/' + service + '/users/' + str(identity['id']) + '/teams/?page_size=200'
        while True:
            rows = listing(path)
            actual = {row['name'] for row in rows}
            require(len(actual) == len(rows) and actual <= expected,
                    'An identity has unexpected direct or inherited team membership.')
            if actual == expected:
                summary['team_membership_checks'] += 1
                return
            require(deadline is not None and time.monotonic() < deadline,
                    'Expected controller team membership did not converge.')
            time.sleep(2)

    def prove_execution(job, key, operation):
        require(str(job.get('inventory')) == str(resource(key, 'inventory')['id']) and
                str(job.get('project')) == str(resource(key, 'project')['id']) and
                str(job.get('job_template')) == str(resource(key, 'jobtemplate', operation)['id']),
                'A launched mock job used unexpected resource bindings.')
        events = listing('/api/controller/v2/jobs/' + str(job['id']) +
                         '/job_events/?event=playbook_on_stats&page_size=200')
        require(len(events) == 1, 'A successful mock job has no unique final execution statistics.')
        stats = events[0].get('event_data', {})
        require(set(stats.get('processed', {})) == {'localhost'} and
                stats.get('processed', {}).get('localhost', 0) >= 1 and
                stats.get('ok', {}).get('localhost', 0) >= 2,
                'A successful mock job did not execute its tasks on localhost.')
        for counter in ('processed', 'ok', 'changed', 'failures', 'dark', 'skipped', 'rescued', 'ignored'):
            require(set(stats.get(counter, {})) <= {'localhost'},
                    'A mock job reports execution on a host other than localhost.')
        require(not any(stats.get('failures', {}).values()) and
                not any(stats.get('dark', {}).values()), 'A mock job reports failed or unreachable tasks.')
        changed = stats.get('changed', {}).get('localhost', 0)
        require((changed == 0 if operation == 'read' else changed >= 1),
                'A mock job did not report the expected read/simulated-change behavior.')
        summary['localhost_execution_verified'] += 1

    def drain_jobs():
        """Wait for every launched job, even if an earlier access check failed."""
        pending = dict(jobs)
        errors = []
        deadline = time.monotonic() + p.get('job_wait_timeout', 1200)
        while pending:
            for job_id, (key, operation) in list(pending.items()):
                try:
                    job = get('/api/controller/v2/jobs/' + str(job_id) + '/')
                except Exception:
                    continue
                status = job.get('status')
                if status not in ('successful', 'failed', 'error', 'canceled'):
                    continue
                del pending[job_id]
                if status != 'successful':
                    errors.append('A launched inert mock job did not complete successfully.')
                    continue
                try:
                    prove_execution(job, key, operation)
                    summary['mock_jobs_verified'] += 1
                except AssertionError as error:
                    errors.append(str(error))
                except Exception:
                    errors.append('Final mock execution statistics could not be verified.')
            if pending and time.monotonic() >= deadline:
                errors.append('Launched mock jobs exceeded the verification deadline.')
                break
            if pending:
                time.sleep(5)
        require(not errors, ' '.join(dict.fromkeys(errors)))

    failure = None
    try:
        if p.get('verify_logins'):
            for user in p['users']:
                gateway_rows = get('/api/gateway/v1/me/', user).get('results', [])
                require(len(gateway_rows) == 1, 'LDAP login returned no unique gateway identity.')
                gateway = gateway_rows[0]
                deadline = time.monotonic() + p.get('convergence_timeout', 60)
                status, data = wait_for_allowed('/api/controller/v2/me/', user, deadline)
                require(status == 200 and len(data.get('results', [])) == 1,
                        'LDAP login returned no unique controller identity.')
                controller = data['results'][0]
                for identity in (gateway, controller):
                    require(identity['username'].lower() == user['username'].lower() and
                            not identity.get('is_superuser') and not identity.get('is_system_auditor') and
                            not identity.get('is_platform_auditor'),
                            'Unexpected identity or global privilege after LDAP login.')
                expected_teams = {prefix + ' ' + ACCESS_LABELS[access] + ' ' + user['role']
                                  for access in ACTOR_ACCESS[user['region']]}
                check_teams('gateway/v1', gateway, expected_teams)
                check_teams('controller/v2', controller, expected_teams, deadline)
                direct = listing('/api/gateway/v1/role_user_assignments/?user=' +
                                 str(gateway['id']) + '&page_size=200')
                require(not any(definitions[str(grant['role_definition'])]['content_type'].startswith('awx.')
                                for grant in direct),
                        'An LDAP identity has individual controller resource grants.')
                allowed = {key for key, (_, access) in RESOURCE_SETS.items()
                           if access in ACTOR_ACCESS[user['region']]}
                for kind, endpoint in ENDPOINTS.items():
                    names = {expected_name(key, kind, operation) for key in allowed
                             for operation in (OPERATIONS if kind == 'jobtemplate' else ('read',))}
                    while True:
                        visible = listing('/api/controller/v2/' + endpoint + '/' + suffix, user)
                        actual_names = {row['name'] for row in visible}
                        require(len(visible) == len(actual_names) and actual_names <= names,
                                'An LDAP identity sees a forbidden or duplicate resource in a list.')
                        if actual_names == names:
                            break
                        require(time.monotonic() < deadline,
                                'Expected resource-list visibility did not converge.')
                        time.sleep(2)
                    summary['resource_list_checks'] += 1
                for key in RESOURCE_SETS:
                    for kind, endpoint in ENDPOINTS.items():
                        obj = resource(key, kind)
                        path = '/api/controller/v2/' + endpoint + '/' + str(obj['id']) + '/'
                        status, visible = (wait_for_allowed(path, user, deadline) if key in allowed
                                           else request(path, user))
                        if key in allowed:
                            require(status == 200, 'Expected resource access did not converge: ' +
                                    user['region'] + '/' + user['role'] + ' -> ' + key + '/' + kind)
                            patch_status, _ = request(path, user, 'PATCH',
                                                      {'description': visible.get('description', '')})
                            require(patch_status == 200 if user['role'] == 'admin' else patch_status in DENIED,
                                    'A resource description PATCH violated the admin-only boundary.')
                            summary['description_patch_checks'] += 1
                        else:
                            require(status in DENIED, 'A forbidden country resource is visible.')
                        summary['permission_checks'] += 1
                    for operation in OPERATIONS:
                        template = resource(key, 'jobtemplate', operation)
                        status, launch = request('/api/controller/v2/job_templates/' +
                                                 str(template['id']) + '/launch/', user, 'POST', {})
                        job_id = launch.get('job') or launch.get('id')
                        # Also drain any unexpectedly accepted forbidden launch before reporting failure.
                        if job_id:
                            require(job_id not in jobs, 'The API returned a duplicate launched job identifier.')
                            jobs[job_id] = (key, operation)
                        permitted = key in allowed and user['role'] in ('executor', 'admin')
                        require(status in (200, 201, 202) and bool(job_id) if permitted else
                                status in DENIED and not job_id,
                                'A mock launch violated the country or reader/executor boundary.')
                        summary['permission_checks'] += 1
                summary['ldap_logins_verified'] += 1
    except Exception as error:
        failure = error
    finally:
        try:
            drain_jobs()
        except Exception as error:
            if failure is None:
                failure = error
            else:
                reason = str(failure) if isinstance(failure, AssertionError) else 'Protected access verification failed.'
                failure = AssertionError(reason + ' Launched mock jobs also failed execution verification.')
    if failure is not None:
        raise failure
    if p.get('verify_logins'):
        require(summary['permission_checks'] == 360 and summary['mock_jobs_verified'] == 36,
                'The completed positive/negative verification totals are incomplete.')
    return summary


def verify(p):
    with tempfile.TemporaryDirectory(prefix='ad-rbac-verification-') as directory:
        ca = Path(directory) / 'ca.pem'
        ca.write_text(p['ca'])
        ca.chmod(0o600)
        context = ssl.create_default_context(cafile=str(ca))
        base = p['url'].rstrip('/')

        def request(path, user=None, method='GET', body=None):
            principal = user or {'username': p['admin_username'], 'password': p['admin_password']}
            authorization = base64.b64encode((principal['username'] + ':' + principal['password']).encode()).decode()
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

        return verify_with_request(p, request)


if __name__ == '__main__':
    try:
        print(json.dumps(verify(json.load(sys.stdin))))
    except Exception as error:
        print(json.dumps({'verified': False, 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError) else 'Protected verification failed.'}))
        raise SystemExit(1)
