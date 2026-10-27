# Exercise production Ansible safety guards offline; see [rationale](README.md#python-tests).
"""Reject widened, changed or unowned Windows teardown target sets."""

import copy
import json
from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.template import Templar


ROOT = Path(__file__).resolve().parents[1]
MARKER = 'aap-disconnected-windows-clone'


class WindowsTeardownScopeTests(unittest.TestCase):
    def setUp(self):
        self.capture = yaml.safe_load((ROOT / 'capture_windows_teardown_baseline.yml').read_text())[0]
        self.verify = yaml.safe_load((ROOT / 'verify_windows_teardown.yml').read_text())[0]
        self.names = ['example-core-one', 'example-core-two', 'example-core-three',
                      'example-core-four', 'example-directory', 'example-extra']
        self.baseline = {
            'domains': {name: {'marker': MARKER, 'xml': '<domain/>', 'state': 'running'}
                        for name in self.names},
            'images': {},
            'target_vm_names': self.names[:4],
        }

    def check(self, play, task_name, names, include_ad=False, baseline=None, item=None):
        baseline = copy.deepcopy(self.baseline if baseline is None else baseline)
        task = next(task for task in play['tasks'] if task['name'] == task_name)
        variables = dict(play.get('vars', {}), windows_demo_vm_names=names,
                         windows_demo_include_ad=include_ad, teardown_baseline=baseline,
                         windows_teardown_baseline={'stdout': json.dumps(baseline)}, item=item)
        loader = DataLoader()
        condition = Conditional(loader=loader)
        conditions = task['ansible.builtin.assert']['that']
        condition.when = conditions if isinstance(conditions, list) else [conditions]
        return condition.evaluate_conditional(Templar(loader=loader, variables=variables), variables)

    def test_fifth_windows_target_requires_explicit_ad_scope_and_six_are_rejected(self):
        for count, include_ad, expected in [(4, False, True), (5, False, False),
                                             (4, True, False), (5, True, True),
                                             (6, True, False)]:
            with self.subTest(count=count, include_ad=include_ad):
                names = self.names[:count]
                baseline = dict(self.baseline, target_vm_names=names)
                self.assertEqual(self.check(
                    self.capture, 'Require the exact declared Windows target count in the baseline',
                    names, include_ad, baseline), expected)
                self.assertEqual(self.check(
                    self.verify, 'Require a pre-teardown baseline and exact target list',
                    names, include_ad, baseline), expected)

    def test_duplicate_and_substituted_targets_cannot_pass_verification(self):
        duplicate = self.names[:3] + [self.names[2]]
        substituted = self.names[:3] + [self.names[4]]
        self.assertFalse(self.check(
            self.capture, 'Require the exact declared Windows target count in the baseline', duplicate))
        for names in [duplicate, substituted]:
            with self.subTest(names=names):
                self.assertFalse(self.check(
                    self.verify, 'Require a pre-teardown baseline and exact target list', names))

    def test_unmarked_domain_is_rejected_by_both_ownership_guards(self):
        baseline = copy.deepcopy(self.baseline)
        baseline['domains'][self.names[0]]['marker'] = 'unrelated-domain'
        for play, task_name in [
            (self.capture, 'Require every selected target to carry the owned Windows clone marker'),
            (self.verify, 'Require the captured target ownership before accepting any removed domain'),
        ]:
            with self.subTest(task=task_name):
                self.assertFalse(self.check(play, task_name, self.names[:4],
                                            baseline=baseline, item=self.names[0]))

    def test_baseline_without_bound_targets_requires_a_fresh_capture(self):
        baseline = copy.deepcopy(self.baseline)
        del baseline['target_vm_names']
        self.assertFalse(self.check(self.verify, 'Require a pre-teardown baseline and exact target list',
                                    self.names[:4], baseline=baseline))


if __name__ == '__main__':
    unittest.main()
