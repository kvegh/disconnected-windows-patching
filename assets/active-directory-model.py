"""Build the regional directory model; all deployed identities come from inputs."""

REGIONS = (('DK', 'Denmark'), ('NO', 'Norway'), ('EU', 'EU'), ('NZ', 'New Zealand'))
ROLES = ('reader', 'executor', 'admin')


def model(prefix, domain):
    base = ','.join('DC=' + label for label in domain.split('.'))
    root = 'OU=' + prefix + ',' + base
    groups = []
    users = []
    ous = [{'name': prefix, 'path': base}]
    for key, label in REGIONS:
        region_dn = 'OU=' + key + ',' + root
        ous.append({'name': key, 'path': root})
        for role in ROLES:
            global_name = '{}-GG-{}-{}'.format(prefix, key, role)
            access_name = '{}-DL-{}-{}'.format(prefix, key, role)
            groups.extend([
                {'name': global_name, 'scope': 'Global', 'path': region_dn,
                 'members': [], 'region': key, 'role': role},
                {'name': access_name, 'scope': 'DomainLocal', 'path': region_dn,
                 'members': [global_name], 'region': key, 'role': role},
            ])
            users.append({'region': key, 'region_label': label, 'role': role,
                          'group': global_name, 'path': region_dn})
    for group in groups:
        if group['scope'] == 'DomainLocal' and group['region'] == 'EU':
            group['members'].extend('{}-GG-{}-{}'.format(prefix, region, group['role'])
                                    for region in ('DK', 'NO'))
    return {'base_dn': base, 'root_dn': root, 'ous': ous, 'groups': groups, 'users': users}
