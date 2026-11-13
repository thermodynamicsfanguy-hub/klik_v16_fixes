"""required_apps follows klik_pos: required where it exists, so an image without it can install this app."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SOURCE = (Path(__file__).resolve().parents[1] / "hooks.py").read_text(encoding="utf-8")


def load(with_klik):
	absent = None if not with_klik else importlib.util.spec_from_loader("klik_pos", loader=None)
	namespace = {}
	with mock.patch("importlib.util.find_spec", side_effect=lambda name: absent if name == "klik_pos" else None):
		exec(compile(SOURCE, "hooks.py", "exec"), namespace)
	return namespace


def required(with_klik):
	return load(with_klik)["required_apps"]


class TestWithoutKlik(unittest.TestCase):
	"""A site without klik_pos must not get handlers that import it (returns.py does, at module level)."""

	def test_no_invoice_handlers_and_no_klik_method_overrides_without_it(self):
		hooks = load(False)
		self.assertEqual(hooks["doc_events"], {})
		self.assertEqual(hooks["override_whitelisted_methods"], {})

	def test_the_zatca_outage_fix_still_runs_without_it(self):
		hooks = load(False)
		self.assertIn("klik_v16_fixes.zatca_outage.apply", hooks["before_request"])
		self.assertIn("klik_v16_fixes.zatca_outage.apply", hooks["before_job"])

	def test_everything_is_registered_with_it(self):
		hooks = load(True)
		self.assertIn("Sales Invoice", hooks["doc_events"])
		self.assertIn("klik_pos.api.sales_invoice.create_and_submit_invoice", hooks["override_whitelisted_methods"])


class TestRequiredApps(unittest.TestCase):
	def test_klik_pos_is_required_where_it_exists(self):
		self.assertEqual(required(True), ["klik_pos"])

	def test_nothing_is_required_where_it_does_not(self):
		self.assertEqual(required(False), [])


if __name__ == "__main__":
	unittest.main()
