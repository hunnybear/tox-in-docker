import unittest
import unittest.mock as mock

import tox_in_docker.main

class Test_Launch(unittest.TestCase):

    @mock.patch('docker.client.DockerClient')
    @mock.patch('tox_in_docker.main.get_test_cmd')
    def test_run_tests(self, get_cmd_mock, client_class_mock):

        client = client_class_mock.return_value
