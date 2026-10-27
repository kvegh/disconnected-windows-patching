# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class ActiveDirectoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        stages = yaml.safe_load((ROOT / 'vars/active_directory_workflow.yml').read_text())['ad_workflow_stages']
        self.stages = {stage['identifier']: stage for stage in stages}
        self.assertEqual(len(self.stages), len(stages), 'Duplicate workflow identifiers')

    def test_every_stage_is_reachable_without_cycles_or_missing_playbooks(self):
        visited, active = set(), set()

        def visit(identifier):
            self.assertNotIn(identifier, active, 'Workflow cycle')
            if identifier in visited:
                return
            stage = self.stages[identifier]
            self.assertTrue((ROOT / stage['playbook']).is_file())
            active.add(identifier)
            for child in stage['successors']:
                visit(child)
            active.remove(identifier)
            visited.add(identifier)

        visit('ad-reserve-address')
        self.assertEqual(visited, set(self.stages))

    def test_ldap_activation_requires_patching_promotion_and_both_tls_checks(self):
        required = {'ad-patch-guest', 'ad-promote-directory', 'ad-configure-ldaps', 'ad-verify-gateway-trust'}

        def visit(identifier, ancestors):
            stage = self.stages[identifier]
            if stage['extra_vars'].get('ad_aap_configure_authentication'):
                self.assertTrue(required <= ancestors)
            for child in stage['successors']:
                visit(child, ancestors | {identifier})

        visit('ad-reserve-address', set())
        self.assertTrue(self.stages['ad-patch-guest']['extra_vars']['ad_direct_microsoft_updates_approved'])
        self.assertTrue(self.stages['ad-verify-gateway-trust']['extra_vars']['ad_trust_verify_ldaps'])
        self.assertTrue(self.stages['ad-verify-aap-access']['extra_vars']['ad_verify_ldap_logins'])


if __name__ == '__main__':
    unittest.main()
