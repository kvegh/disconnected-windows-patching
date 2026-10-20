"""Read-only topology evidence must distinguish permanent NICs from live hotplug."""

import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).parents[1] / 'assets' / 'inspect-activation-domain.py'
SPEC = importlib.util.spec_from_file_location('activation_domain', PATH)
DOMAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOMAIN)

XML = '''<domain><name>demo-clone</name><uuid>00000000-0000-0000-0000-000000000001</uuid>
<description>aap-disconnected-windows-clone</description><devices>
<interface type="network"><mac address="52:54:00:11:22:33"/>
<source network="isolated-example"/><model type="e1000e"/></interface>
{extra}</devices></domain>'''
EXTRA = '''<interface type="network"><mac address="52:54:00:44:55:66"/>
<source network="activation-example"/><model type="e1000e"/><link state="down"/></interface>'''


class ActivationDomainTests(unittest.TestCase):
    def test_temporary_live_nic_is_not_confused_with_persistent_topology(self):
        calls = []

        def run(argv, text):
            calls.append(argv)
            if 'list' in argv:
                return 'demo-clone\n'
            return XML.format(extra='' if '--inactive' in argv else EXTRA)

        result = DOMAIN.inspect('demo-clone', run)
        self.assertTrue(result['running'])
        self.assertEqual(result['marker'], 'aap-disconnected-windows-clone')
        self.assertEqual(len(result['persistent']), 1)
        self.assertEqual(len(result['live']), 2)
        self.assertEqual(result['live'][1]['link'], 'down')
        self.assertTrue(all(call[:3] == ['virsh', '--connect', 'qemu:///system'] for call in calls))
        self.assertTrue(all(any(op in call for op in ['list', 'dumpxml']) for call in calls))

    def test_changed_network_is_detectable_even_with_same_mac(self):
        before = DOMAIN.interfaces(XML.format(extra=''))
        after = DOMAIN.interfaces(XML.format(extra='').replace('isolated-example', 'connected-example'))
        self.assertNotEqual(before, after)
        self.assertEqual(before[0]['mac'], after[0]['mac'])

    def test_xml_interface_order_does_not_hide_or_invent_changes(self):
        first = DOMAIN.interfaces(XML.format(extra=EXTRA))
        reordered = XML.format(extra=EXTRA).replace('52:54:00:11:22:33', '52:54:00:AA:BB:CC')
        self.assertNotEqual(first, DOMAIN.interfaces(reordered))
        self.assertEqual(first, sorted(first, key=lambda item: item['mac']))


if __name__ == '__main__':
    unittest.main()
