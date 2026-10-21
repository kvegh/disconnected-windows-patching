"""Check effective nested regional access without Windows or AAP dependencies."""

import importlib.util
from pathlib import Path
import unittest
import yaml

SPEC = importlib.util.spec_from_file_location(
    'ad_model', Path(__file__).parents[1] / 'assets/active-directory-model.py')
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


class RegionalAccessTests(unittest.TestCase):
    def setUp(self):
        self.model = MODEL.model('Synthetic', 'example.test')
        self.groups = {item['name']: item for item in self.model['groups']}

    def access(self, region, role):
        memberships = {'Synthetic-GG-{}-{}'.format(region, role)}
        while True:
            expanded = memberships | {name for name, group in self.groups.items()
                                       if memberships.intersection(group['members'])}
            if expanded == memberships:
                break
            memberships = expanded
        return {(group['region'], group['role']) for name, group in self.groups.items()
                if name in memberships and group['scope'] == 'DomainLocal'}

    def test_each_country_receives_only_its_matching_role_and_eu_role(self):
        for region in ('DK', 'NO'):
            for role in MODEL.ROLES:
                with self.subTest(region=region, role=role):
                    self.assertEqual(self.access(region, role), {(region, role), ('EU', role)})

    def test_new_zealand_never_inherits_european_access(self):
        for role in MODEL.ROLES:
            self.assertEqual(self.access('NZ', role), {('NZ', role)})

    def test_eu_membership_does_not_grant_country_access(self):
        for role in MODEL.ROLES:
            self.assertEqual(self.access('EU', role), {('EU', role)})

    def test_no_role_inherits_a_more_privileged_role(self):
        for region, _ in MODEL.REGIONS:
            for role in MODEL.ROLES:
                self.assertEqual({item[1] for item in self.access(region, role)}, {role})

    def test_aap_region_keys_preserve_norway_as_a_string(self):
        path = Path(__file__).parents[1] / 'configure_aap_ad_regions.yml'
        regions = yaml.safe_load(path.read_text())[0]['vars']['ad_region_labels']
        self.assertEqual(set(regions), {'DK', 'NO', 'EU', 'NZ'})


if __name__ == '__main__':
    unittest.main()
