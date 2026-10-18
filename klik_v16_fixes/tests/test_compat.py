"""Fails when a KLiK update breaks something this app's fixes rely on (see compat.py).

    bench --site <site> run-tests --app klik_v16_fixes --module klik_v16_fixes.tests.test_compat
"""

from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from klik_v16_fixes import compat


class TestKlikCompat(IntegrationTestCase):
	def test_installed_klik_matches_the_fixes(self):
		self.assertEqual(compat.problems(), [])

	def test_reports_a_renamed_page_label(self):
		bundle, _files = compat.klik_bundle_text()
		found = compat.problems(bundle_text=bundle.replace("Write-off:", "Writeoff:"))
		self.assertTrue(any(line.startswith("return_refund.js") and "Write-off:" in line for line in found), found)

	def test_reports_a_vanished_klik_function(self):
		gone = ("klik_pos.api.sales_invoice", "no_such_function", None, "returns.py")
		with patch.object(compat, "FUNCTIONS", [*compat.FUNCTIONS, gone]):
			found = compat.problems()
		self.assertIn("returns.py: klik_pos.api.sales_invoice.no_such_function no longer exists", found)
