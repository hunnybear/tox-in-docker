
import unittest
from unittest import mock

import tox

from tox_in_docker import plugin

from .util import AnyStr

class TestCase(unittest.TestCase):

	def test_add_option(self):

		parser_mock = mock.Mock(spec=tox.config.Parser())

		res = plugin.tox_addoption(parser_mock)

		parser_mock.add_argument.assert_has_calls([
				mock.call('--in_docker', action='store_true', dest='always_in_docker', default=None),
				mock.call('--no_tox_in_docker', action='store_false', 
					      default=None, dest='in_docker', help=AnyStr)
			],
			any_order=True)

		self.assertIsNone(res)

