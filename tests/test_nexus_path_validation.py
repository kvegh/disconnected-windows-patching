import os
from pathlib import Path
import unittest

os.environ.setdefault("ANSIBLE_LOCAL_TEMP", "/tmp/aap-ansible-tmp")

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.template import Templar


class NexusPathValidationTests(unittest.TestCase):
    def test_absolute_paths_are_checked_with_ansibles_conditional_parser(self):
        # Output-expression templating escapes backslashes differently from
        # assert/when conditionals; exercise the parser used by the live task.
        play = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "setup_chocolatey.yml").read_text()
        )[1]
        checks = [
            expression
            for expression in play["pre_tasks"][0]["ansible.builtin.assert"]["that"]
            if "is regex" in expression
        ]
        import_play = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "replicate_and_import_chocolatey.yml").read_text()
        )[0]
        checks.extend(
            expression
            for expression in import_play["tasks"][0]["ansible.builtin.assert"]["that"]
            if "chocolatey_transfer_directory is regex" in expression
        )
        self.assertEqual(3, len(checks))
        cases = [
            (r"C:\Nexus", True),
            (r"C:\NexusData", True),
            (r"D:\Demo\Nexus-3.96.4-01", True),
            (r"C:Nexus", False),
            ("Nexus", False),
            (r"\\server\share", False),
            ('C:\\Nexus"', False),
            ("C:\\Nexus\n", False),
        ]
        loader = DataLoader()
        for expression in checks:
            for value, expected in cases:
                with self.subTest(expression=expression, value=value):
                    variables = {
                        "nexus_install_root": value,
                        "nexus_data_directory": value,
                        "chocolatey_transfer_directory": value,
                    }
                    condition = Conditional(loader=loader)
                    condition.when = [expression]
                    actual = condition.evaluate_conditional(
                        Templar(loader=loader, variables=variables), variables
                    )
                    self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
