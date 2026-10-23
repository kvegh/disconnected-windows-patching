"""Build a guarded, read-only plan for migrating this demo's AAP objects.

Protected input is JSON on stdin. Only existing owned object IDs and desired
names are returned; Ansible performs any subsequent changes.
"""

import base64
import json
from pathlib import Path
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


RESOURCE_SETS = ('DKlocal', 'NOlocal', 'DKEUapproved', 'NOEUapproved', 'NZlocal')
LEGACY_RESOURCE_LABELS = {
    'DKlocal': 'Denmark', 'NOlocal': 'Norway',
    'DKEUapproved': 'EU', 'NZlocal': 'New Zealand',
}
TEAM_SCOPES = {
    'DKlocal': 'Denmark', 'NOlocal': 'Norway',
    'EUapproved': 'EU', 'NZlocal': 'New Zealand',
}
ROLES = ('reader', 'executor', 'admin')
SUFFIXES = {
    'inventory': ('Inventory', 'Mock Inventory'),
    'credential': ('Credential', 'Mock Credential'),
    'read': ('Read', 'read'),
    'simulate_change': ('Simulate Change', 'simulate_change'),
}
SOURCE_URL = 'https://github.com/kvegh/disconnected-windows-patching.git'
LDAP_TYPE = 'ansible_base.authentication.authenticator_plugins.ldap'


def identifier(value):
    """Accept positive numeric IDs without accepting booleans or expressions."""
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise AssertionError('An inspection object has an invalid numeric ID.')
    return str(int(value))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AssertionError('Inspection API redirects are not permitted.')


class API:
    def __init__(self, parameters, ca_file):
        self.base = parameters['url'].rstrip('/')
        parsed = urllib.parse.urlsplit(self.base)
        if (parsed.scheme != 'https' or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or parsed.path):
            raise AssertionError('Inspection requires an HTTPS platform root URL.')
        self.origin = (parsed.scheme, parsed.netloc)
        context = ssl.create_default_context(cafile=str(ca_file))
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), NoRedirect())
        token = base64.b64encode(
            (parameters['admin_username'] + ':' + parameters['admin_password']).encode()).decode()
        self.headers = {'Authorization': 'Basic ' + token, 'Accept': 'application/json'}

    def get(self, path):
        url = urllib.parse.urljoin(self.base + '/', path)
        parsed = urllib.parse.urlsplit(url)
        if ((parsed.scheme, parsed.netloc) != self.origin or parsed.username
                or parsed.password or parsed.fragment
                or not parsed.path.startswith(('/api/gateway/v1/', '/api/controller/v2/'))):
            raise AssertionError('An inspection API link is outside the selected platform.')
        request = urllib.request.Request(url, headers=self.headers, method='GET')
        try:
            with self.opener.open(request, timeout=60) as response:
                if response.status != 200:
                    raise AssertionError('An inspection API read returned an unexpected status.')
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise AssertionError('An inspection API read failed: HTTP ' + str(error.code)) from None
        if not isinstance(data, dict):
            raise AssertionError('An inspection API response has an unexpected format.')
        return data

    def listing(self, path):
        results = []
        seen_pages = set()
        while path:
            if path in seen_pages or len(seen_pages) >= 1000:
                raise AssertionError('Inspection API pagination did not converge.')
            seen_pages.add(path)
            data = self.get(path)
            if not isinstance(data.get('results'), list):
                raise AssertionError('An inspection API listing has an unexpected format.')
            results.extend(data['results'])
            path = data.get('next')
        ids = [identifier(item.get('id')) for item in results]
        if len(ids) != len(set(ids)):
            raise AssertionError('An inspection listing contains duplicate object IDs.')
        return results


def selected(objects, names, kind):
    matches = [item for item in objects if item.get('name') in names]
    if len(matches) > 1:
        raise AssertionError('Both legacy and desired ' + kind + ' candidates exist, or a name is duplicated.')
    return matches[0] if matches else None


def organization_id(item):
    value = item.get('organization')
    if isinstance(value, dict):
        value = value.get('id')
    return identifier(value)


def owned_listing(api, endpoint, organization, allowed_names, kind, gateway=False):
    base = '/api/gateway/v1/' if gateway else '/api/controller/v2/'
    objects = api.listing(base + endpoint + '/?organization=' + organization + '&page_size=200')
    for item in objects:
        if organization_id(item) != organization or item.get('name') not in allowed_names:
            raise AssertionError('An unexpected or differently owned ' + kind + ' is in the demo organization.')
    return objects


def inspect(parameters):
    prefix = parameters['prefix']
    if (not isinstance(prefix, str) or not prefix or prefix != prefix.strip()
            or any(character.isspace() for character in prefix)):
        raise AssertionError('The demo prefix is invalid.')
    if parameters['authenticator_name'] != prefix + ' Active Directory':
        raise AssertionError('The selected authenticator is outside the owned demo naming scope.')

    names = {}
    resources = {}
    for key in RESOURCE_SETS:
        names[key] = {}
        resources[key] = {}
        for kind, (desired_suffix, legacy_suffix) in SUFFIXES.items():
            desired = key + ' ' + desired_suffix
            candidates = {desired}
            if key in LEGACY_RESOURCE_LABELS:
                candidates.add(prefix + ' ' + LEGACY_RESOURCE_LABELS[key] + ' ' + legacy_suffix)
            names[key][kind] = candidates
            resources[key][kind] = desired
    teams = {scope: {role: prefix + ' ' + scope + ' ' + role for role in ROLES}
             for scope in TEAM_SCOPES}
    plan = {'resources': resources, 'teams': teams, 'old_project': None,
            'retired_users': [], 'retired_usernames': []}

    with tempfile.TemporaryDirectory(prefix='ad-aap-migration-inspection-') as directory:
        ca = Path(directory) / 'ca.pem'
        ca.write_text(parameters['ca'], encoding='utf-8')
        ca.chmod(0o600)
        api = API(parameters, ca)
        organization_name = prefix + ' Regional Identity Demo'
        organizations = api.listing('/api/gateway/v1/organizations/?'
                                    + urllib.parse.urlencode({'name': organization_name, 'page_size': 200}))
        if len(organizations) > 1 or any(item.get('name') != organization_name for item in organizations):
            raise AssertionError('The owned demo organization is not unique.')
        if not organizations:
            if parameters.get('require_migrated'):
                raise AssertionError('The final demo organization is missing.')
            return plan
        organization = identifier(organizations[0]['id'])

        collections = {}
        for kind, endpoint in (('inventory', 'inventories'), ('credential', 'credentials')):
            allowed = set().union(*(names[key][kind] for key in RESOURCE_SETS))
            collections[kind] = owned_listing(api, endpoint, organization, allowed, kind)
        allowed_templates = set().union(*(names[key][kind] for key in RESOURCE_SETS
                                         for kind in ('read', 'simulate_change')))
        templates = owned_listing(api, 'job_templates', organization, allowed_templates, 'job template')
        collections['read'] = templates
        collections['simulate_change'] = templates

        resolved = {}
        for key in RESOURCE_SETS:
            resolved[key] = {}
            for kind in SUFFIXES:
                item = selected(collections[kind], names[key][kind], kind)
                if item:
                    resources[key][kind] = identifier(item['id'])
                    resolved[key][kind] = item
                if parameters.get('require_migrated') and (
                        not item or item.get('name') != key + ' ' + SUFFIXES[kind][0]):
                    raise AssertionError('An owned resource is missing or still uses its legacy name.')

        old_project_name = prefix + ' Regional Mock Resources'
        project_names = set(RESOURCE_SETS)
        projects = owned_listing(api, 'projects', organization, project_names | {old_project_name}, 'project')
        projects_by_key = {}
        for name in project_names | {old_project_name}:
            project = selected(projects, {name}, 'project')
            if not project:
                continue
            if (project.get('scm_type') != 'git' or project.get('scm_url') != SOURCE_URL
                    or project.get('scm_branch') != 'main'):
                raise AssertionError('An owned mock project does not use the approved public Git source and branch.')
            project_id = identifier(project['id'])
            if name == old_project_name:
                plan['old_project'] = project_id
            else:
                projects_by_key[name] = project_id
        if parameters.get('require_migrated') and set(projects_by_key) != project_names:
            raise AssertionError('A final resource-set project is missing.')

        for key in RESOURCE_SETS:
            for kind in ('read', 'simulate_change'):
                template = resolved[key].get(kind)
                if not template:
                    continue
                if template.get('playbook') != 'mock_regional_job.yml':
                    raise AssertionError('An owned mock template uses an unexpected playbook.')
                inventory = resolved[key].get('inventory')
                credential = resolved[key].get('credential')
                if (not inventory or not credential
                        or identifier(template.get('inventory')) != identifier(inventory['id'])):
                    raise AssertionError('An owned mock template does not use its owned resource-set inventory.')
                permitted_projects = {value for value in (
                    None if parameters.get('require_migrated') else plan['old_project'],
                    projects_by_key.get(key)) if value}
                if identifier(template.get('project')) not in permitted_projects:
                    raise AssertionError('An owned mock template does not use its owned mock project.')
                credentials = api.listing('/api/controller/v2/job_templates/'
                                          + identifier(template['id']) + '/credentials/?page_size=200')
                if (len(credentials) != 1
                        or identifier(credentials[0]['id']) != identifier(credential['id'])
                        or organization_id(credentials[0]) != organization):
                    raise AssertionError('An owned mock template does not use only its owned mock credential.')

        if parameters.get('require_migrated') and plan['old_project']:
            for endpoint, query in (('job_templates', 'project'),
                                    ('workflow_job_template_nodes', 'unified_job_template')):
                references = api.listing('/api/controller/v2/' + endpoint + '/?'
                                         + query + '=' + plan['old_project'] + '&page_size=200')
                if references:
                    raise AssertionError('The retired shared mock project still has template or workflow references.')

        allowed_teams = {prefix + ' ' + label + ' ' + role
                         for scope, legacy in TEAM_SCOPES.items()
                         for label in (scope, legacy) for role in ROLES}
        existing_teams = owned_listing(api, 'teams', organization, allowed_teams, 'team', gateway=True)
        for scope, legacy in TEAM_SCOPES.items():
            for role in ROLES:
                team = selected(existing_teams, {teams[scope][role], prefix + ' ' + legacy + ' ' + role}, 'team')
                if team:
                    teams[scope][role] = identifier(team['id'])
                if parameters.get('require_migrated') and (
                        not team or team.get('name') != prefix + ' ' + scope + ' ' + role):
                    raise AssertionError('An owned team is missing or still uses its legacy name.')

        authenticators = api.listing('/api/gateway/v1/authenticators/?'
                                    + urllib.parse.urlencode({'name': parameters['authenticator_name'], 'page_size': 200}))
        if len(authenticators) > 1 or any(item.get('name') != parameters['authenticator_name'] for item in authenticators):
            raise AssertionError('The owned LDAP authenticator is not unique.')
        authenticator = authenticators[0] if authenticators else None
        if authenticator and authenticator.get('type') != LDAP_TYPE:
            raise AssertionError('The owned authenticator is not an LDAP authenticator.')
        authenticator_id = identifier(authenticator['id']) if authenticator else None
        for role in ROLES:
            username = prefix.lower() + '-eu-' + role
            users = api.listing('/api/gateway/v1/users/?'
                                + urllib.parse.urlencode({'username': username, 'page_size': 200}))
            if len(users) > 1 or any(user.get('username') != username for user in users):
                raise AssertionError('A retired demo identity is not unique.')
            for user in users:
                associations = user.get('associated_authenticators')
                if (user.get('is_superuser') is not False or user.get('is_platform_auditor') is not False
                        or user.get('is_system_auditor', False) is not False
                        or not isinstance(associations, dict) or authenticator_id not in associations):
                    raise AssertionError('A retired demo identity does not satisfy the owned LDAP-user safeguards.')
                plan['retired_users'].append(identifier(user['id']))
                plan['retired_usernames'].append(username)
        return plan


if __name__ == '__main__':
    try:
        print(json.dumps(inspect(json.load(sys.stdin))))
    except Exception as error:
        print(json.dumps({'inspected': False, 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, AssertionError)
                          else 'Protected migration inspection failed.'}))
        raise SystemExit(1)
