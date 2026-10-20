"""Check the actual Ansible filters used across Windows update/reboot cycles.

Run with a Python interpreter containing the existing ansible-core and PyYAML:
    python3.12 -m unittest discover -s tests -p 'test_windows_patching_filters.py'
No controller, WSUS connection, or additional test framework is needed.
"""

import re
import unittest
from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar


ROOT = Path(__file__).resolve().parents[1]


class WindowsPatchingFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        play = yaml.safe_load((ROOT / "update_managed_windows.yml").read_text())[1]
        cls.fact_templates = {}
        for task in play["tasks"]:
            cls.fact_templates.update(task.get("ansible.builtin.set_fact", {}))
        cls.months = yaml.safe_load((ROOT / "vars/wsus_patch_month.yml").read_text())[
            "wsus_patch_month_choices"
        ]

    def filters(self, month, titles=()):
        values = {
            "windows_patch_active_month": month,
            "wsus_patch_month_choices": self.months,
            "windows_patch_allowed_updates": [{"title": title} for title in titles],
        }
        templar = Templar(loader=DataLoader(), variables=values)
        values["windows_patch_release_filter"] = templar.template(
            self.fact_templates["windows_patch_release_filter"]
        )
        templar.available_variables = values
        return templar.template(self.fact_templates["windows_patch_eligibility_filters"])

    @staticmethod
    def accepted(filters, title):
        return any(re.search(pattern, title) for pattern in filters)

    def test_april_accepts_component_titles_and_older_checkpoints(self):
        filters = self.filters("2026-04")
        for title in (
            "2026-04 Cumulative Update for .NET Framework (KB5082427)",
            "2026-04 Cumulative Update for .NET Framework (KB5082425)",
            "2026-04 Cumulative Update for Windows Server (KB5082142)",
            "2026-02 Servicing Stack Update for Windows Server",
            "2025-09 Checkpoint Cumulative Update for Windows Server",
        ):
            with self.subTest(title=title):
                self.assertTrue(self.accepted(filters, title))

    def test_april_blocks_later_and_unknown_release_titles(self):
        filters = self.filters("2026-04")
        for title in (
            "2026-05 Cumulative Update for Windows Server",
            "2026-09 Cumulative Update for .NET Framework",
            "2027-01 Cumulative Update for Windows Server",
            "2026-040 Cumulative Update for Windows Server",
            "An update with no audited release month",
        ):
            with self.subTest(title=title):
                self.assertFalse(self.accepted(filters, title))

    def test_advancing_the_month_allows_the_next_release(self):
        title = "2026-05 Cumulative Update for Windows Server"
        self.assertFalse(self.accepted(self.filters("2026-04"), title))
        self.assertTrue(self.accepted(self.filters("2026-05"), title))

    def test_audited_undated_prerequisite_uses_a_literal_title(self):
        title = "Servicing (x64) + prerequisite [KB1234567]"
        filters = self.filters("2026-04", [title])
        self.assertTrue(self.accepted(filters, title))
        self.assertFalse(self.accepted(filters, "Servicing x64 prerequisite K"))
        self.assertFalse(self.accepted(filters, title + " newer"))

    def test_dated_parent_titles_do_not_restrict_component_matching(self):
        filters = self.filters(
            "2026-04", ["2026-04 Cumulative Update for .NET (KB5084071)"]
        )
        self.assertEqual(len(filters), 1)
        self.assertTrue(
            self.accepted(filters, "2026-04 Cumulative Update for .NET (KB5082427)")
        )

    def test_install_pass_allows_only_observed_client_titles(self):
        tasks = yaml.safe_load((ROOT / "tasks/update_managed_windows_pass.yml").read_text())[0]["block"]
        expression = next(
            task["ansible.builtin.set_fact"]["windows_patch_cycle_accept_list"]
            for task in tasks
            if "windows_patch_cycle_accept_list" in task.get("ansible.builtin.set_fact", {})
        )
        observed = "2026-04 Cumulative Update for .NET (KB5082427) [x64]"
        variables = {"windows_patch_cycle_scan": {"result": {"updates": {"component-guid": {"title": observed}}}}}
        filters = Templar(loader=DataLoader(), variables=variables).template(expression)
        self.assertTrue(self.accepted(filters, observed))
        self.assertFalse(self.accepted(filters, observed + " newer"))
        self.assertFalse(self.accepted(filters, "2026-04 Cumulative Update for .NET (KB5082425)"))

    def test_zero_offers_do_not_pass_a_below_baseline_os_build(self):
        tasks = yaml.safe_load((ROOT / "tasks/update_managed_windows_host.yml").read_text())[0]["block"]
        assertion = next(
            task["ansible.builtin.assert"]["that"]
            for task in tasks
            if task["name"] == "Require the audited OS baseline and no outstanding update or reboot"
        )
        for comparison, expected in (("below", False), ("at", True), ("above", True)):
            variables = {
                "windows_patch_before": {"result": {"build_family": "20348"}},
                "windows_patch_after": {"result": {"build_family": "20348", "reboot_pending": False}},
                "windows_patch_baseline_comparison": comparison,
                "windows_patch_scan_after": {"result": {"found_update_count": 0, "reboot_required": False}},
            }
            templar = Templar(loader=DataLoader(), variables=variables)
            with self.subTest(comparison=comparison):
                self.assertEqual(all(templar.template("{{ " + item + " }}") for item in assertion), expected)


if __name__ == "__main__":
    unittest.main()
