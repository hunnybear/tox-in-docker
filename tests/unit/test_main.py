import unittest
import unittest.mock as mock

import tox_in_docker.main

class Test_Launch(unittest.TestCase):

    @mock.patch('tox_in_docker.main.do_launch')
    def test_do_tests(self, do_launch_mock):
        tox_in_docker.main.do_tests()

        do_launch_mock.assert_called_once()

