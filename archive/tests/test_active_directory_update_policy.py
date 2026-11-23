# Exercise production Python and Ansible behavior offline; see [rationale](README.md#python-tests).
"""Keep the Server applicability exception narrower than Defender servicing."""
from pathlib import Path
import re
import unittest
import yaml


class ServerUpdateApplicabilityTests(unittest.TestCase):
    def test_windows11_ui_exception_preserves_server_and_defender_updates(self):
        play = yaml.safe_load((Path(__file__).parents[1] / 'prepare_active_directory_guest.yml').read_text())[0]
        operations = [task['ansible.windows.win_updates'] for task in play['tasks']
                      if 'ansible.windows.win_updates' in task]
        self.assertEqual(len(operations), 2, 'Check both update installation and the final search')
        self.assertEqual({operation['state'] for operation in operations}, {'installed', 'searched'})
        for operation in operations:
            excluded = lambda title: any(re.search(pattern, title, re.I) for pattern in operation['reject_list'])
            self.assertTrue(excluded('Update for Windows Security platform - KB5007651 (Version 10.0.27703.1006)'))
            for title in [
                'Update for Microsoft Defender Antivirus antimalware platform - KB4052623',
                'Security Intelligence Update for Microsoft Defender Antivirus - KB2267602',
                'Cumulative Update for Windows Server 2025 - KB5126646',
                'Update for Windows Security platform - KB50076510',
                'Cumulative Update for .NET Framework for Windows Server 2025',
            ]:
                with self.subTest(title=title, state=operation['state']):
                    self.assertFalse(excluded(title))


if __name__ == '__main__':
    unittest.main()
