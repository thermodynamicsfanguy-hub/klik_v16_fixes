"""required_apps follows klik_pos: required where it exists, so an image without it can install this app."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SOURCE = (Path(__file__).resolve().parents[1] / "hooks.py").read_text(encoding="utf-8")


def required(with_klik):
	absent = None if not with_klik else importlib.util.spec_from_loader("klik_pos", loader=None)
	namespace = {}
	with mock.patch("importlib.util.find_spec", side_effect=lambda name: absent if name == "klik_pos" else None):
		exec(compile(SOURCE, "hooks.py", "exec"), namespace)
	return namespace["required_apps"]


class TestRequiredApps(unittest.TestCase):
	def test_klik_pos_is_required_where_it_exists(self):
		self.assertEqual(required(True), ["klik_pos"])

	def test_nothing_is_required_where_it_does_not(self):
		self.assertEqual(required(False), [])


if __name__ == "__main__":
	unittest.main()
