"""Separate actor countries, access scopes and country-owned resource sets."""

REGIONS = (('DK', 'Denmark'), ('NO', 'Norway'), ('NZ', 'New Zealand'), ('HU', 'Hungary'))
ACCESS_SCOPES = ('DK', 'NO', 'EU', 'NZ')
ACTOR_ACCESS = {'DK': ('DK', 'EU'), 'NO': ('NO', 'EU'),
                'NZ': ('NZ',), 'HU': ('EU',)}
RESOURCE_SETS = (
    ('DKlocal', 'DK', 'DK'),
    ('NOlocal', 'NO', 'NO'),
    ('DKEUapproved', 'DK', 'EU'),
    ('NOEUapproved', 'NO', 'EU'),
    ('NZlocal', 'NZ', 'NZ'),
)
ROLES = ('reader', 'executor', 'admin')


def model(prefix, domain):
    base = ','.join('DC=' + label for label in domain.split('.'))
    root = 'OU=' + prefix + ',' + base
    groups = []
    users = []
    ous = [{'name': prefix, 'path': base}]
    retired_users = []
    retired_groups = []
    for key, label in REGIONS:
        region_dn = 'OU=' + key + ',' + root
        ous.append({'name': key, 'path': root})
        for role in ROLES:
            global_name = '{}-GG-{}-{}'.format(prefix, key, role)
            groups.append({'name': global_name, 'scope': 'Global', 'path': region_dn,
                           'members': [], 'region': key, 'role': role})
            users.append({'region': key, 'region_label': label, 'role': role,
                          'username': '{}-{}-{}'.format(prefix.lower(), key.lower(), role),
                          'group': global_name, 'path': region_dn})
    # EU is an access scope, rather than an actor country or resource owner.
    eu_path = 'OU=EU,' + root
    ous.append({'name': 'EU', 'path': root})
    for access in ACCESS_SCOPES:
        for role in ROLES:
            groups.append({
                'name': '{}-DL-{}-{}'.format(prefix, access, role),
                'scope': 'DomainLocal', 'path': 'OU=' + access + ',' + root,
                'members': ['{}-GG-{}-{}'.format(prefix, country, role)
                            for country, _ in REGIONS if access in ACTOR_ACCESS[country]],
                'region': access, 'role': role,
            })
    for role in ROLES:
        retired_users.append({'username': '{}-eu-{}'.format(prefix.lower(), role),
                              'path': eu_path, 'region': 'EU', 'role': role})
        retired_groups.append({'name': '{}-GG-EU-{}'.format(prefix, role),
                               'path': eu_path, 'scope': 'Global',
                               'region': 'EU', 'role': role})
    resources = [{'key': key, 'owner': owner, 'access': access}
                 for key, owner, access in RESOURCE_SETS]
    return {'base_dn': base, 'root_dn': root, 'ous': ous, 'groups': groups,
            'users': users, 'retired_users': retired_users,
            'retired_groups': retired_groups, 'resource_sets': resources}
