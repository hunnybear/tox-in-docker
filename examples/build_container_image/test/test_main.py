from unittest import mock
import unittest
from build_container_image import main


class TestMain(unittest.TestCase):

	def test_ping(self):
		self.assertIsInstance(main.ping(), bytes)
