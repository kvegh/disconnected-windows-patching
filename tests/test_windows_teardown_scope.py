"""Exercise real reset guards against changed scope and preserved core evidence."""
import copy
import json
from pathlib import Path
import unittest
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.template import Templar

ROOT = Path(__file__).resolve().parents[1]

class WindowsTeardownScopeTests(unittest.TestCase):
    def setUp(self):
        self.capture = yaml.safe_load((ROOT / 'capture_windows_teardown_baseline.yml').read_text())[0]
        self.verify = yaml.safe_load((ROOT / 'verify_windows_teardown.yml').read_text())[0]
        self.names = ['example-ext', 'example-int', 'example-win22', 'example-win25', 'example-ad']
        self.owned = {name: {'uuid': 'fixture', 'disk': '/opt/vms/win-' + name + '-clone.disk.qcow2',
                              'interfaces': []} for name in self.names}
        self.baseline = {'core_before_deployment': True, 'domains': {'core': {'xml': '<domain/>', 'state': 'running'}},
                         'images': {'golden': {'inode': 1}}, 'target_vm_names': self.names,
                         'windows_owned': self.owned, 'ad_before': {'prefix': 'Example'}}

    def check(self, play, name, values):
        task = next(task for task in play['tasks'] if task['name'] == name)
        loader = DataLoader(); condition = Conditional(loader=loader)
        conditions = task['ansible.builtin.assert']['that']
        condition.when = conditions if isinstance(conditions, list) else [conditions]
        return condition.evaluate_conditional(Templar(loader=loader, variables=values), values)

    def values(self):
        return dict(self.verify.get('vars', {}), teardown_baseline=copy.deepcopy(self.baseline),
                    windows_demo_vm_names=self.names, windows_demo_include_ad=True,
                    windows_decommission_preview={'instance': 'example', 'read_only': True, 'domains': self.owned})

    def test_final_reset_requires_original_core_and_exact_five_actual_owners(self):
        values = self.values()
        name = 'Require a pre-teardown baseline and exact target list'
        self.assertTrue(self.check(self.verify, name, values))
        for kind in ('wrong-counter', 'duplicate', 'legacy-baseline', 'changed-owner'):
            bad = copy.deepcopy(values)
            if kind == 'wrong-counter': bad['windows_demo_vm_names'] = ['foreign'] + self.names[1:]
            if kind == 'duplicate': bad['windows_demo_vm_names'] = self.names[:-1] + [self.names[0]]
            if kind == 'legacy-baseline': bad['teardown_baseline']['core_before_deployment'] = False
            if kind == 'changed-owner': bad['teardown_baseline']['windows_owned'][self.names[0]]['uuid'] = 'foreign'
            with self.subTest(kind=kind):
                self.assertFalse(self.check(self.verify, name, bad))

    def test_initial_snapshot_refuses_any_existing_selected_domain(self):
        name = 'Require selected clones absent before the original core capture'
        values = {'windows_demo_vm_names': self.names,
                  'windows_teardown_baseline': {'stdout': json.dumps({'domains': {'core': {}}})}}
        self.assertTrue(self.check(self.capture, name, values))
        values['windows_teardown_baseline']['stdout'] = json.dumps({'domains': {self.names[0]: {}}})
        self.assertFalse(self.check(self.capture, name, values))

    def test_later_capture_rejects_changed_core_images_or_target_ownership(self):
        name = 'Require the original core images and domains when appending cleanup evidence'
        current = {'domains': dict(self.baseline['domains'], **{name: {} for name in self.names}),
                   'images': self.baseline['images']}
        values = dict(self.values(), windows_teardown_baseline={'stdout': json.dumps(current)},
                      windows_decommission_owned_preview={'stdout': json.dumps({'domains': self.owned})})
        self.assertTrue(self.check(self.capture, name, values))
        current['images'] = {'golden': {'inode': 2}}
        values['windows_teardown_baseline']['stdout'] = json.dumps(current)
        self.assertFalse(self.check(self.capture, name, values))

    def test_append_retains_original_core_and_images(self):
        task = next(task for task in self.capture['tasks'] if task['name'].startswith('Append actual cleanup'))
        values = dict(self.values(), windows_decommission_owned_preview={'stdout': json.dumps({'domains': self.owned})},
                      windows_ad_ownership={'stdout': json.dumps({'prefix': 'Example', 'users': []})})
        rendered = Templar(loader=DataLoader(), variables=values).template(task['ansible.builtin.set_stats']['data'])
        for key in ('domains', 'images', 'target_vm_names', 'ad_before'):
            self.assertEqual(rendered['teardown_baseline'][key], self.baseline[key])

if __name__ == '__main__': unittest.main()
