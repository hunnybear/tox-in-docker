import unittest
import unittest.mock as mock

import tox_in_docker.main

ENV_NAME = 'my_env'
IMAGE_TAG = 'my_image:oldest'


def


@mock.patch('__main__.open', mock.mock_open())
@mock.patch('tempfile.TemporaryDirectory')
@mock.patch('docker.client.DockerClient')
class Test_Launch(unittest.TestCase):

    def test_run_tests_explicit_image(
            self,
            client_class_mock,
            temporary_directory_mock,
            open_mock):

        client_mock = client_class_mock.return_value

        tox_in_docker.main.run_tests(ENV_NAME, image=IMAGE_TAG)

        client_mock.containers.run.assert_called_once_with(
            ENV_NAME,
            image=IMAGE_TAG,
            # might be nice to enforce dict
            volumes=mock.ANY,
            entrypoint=mock.ANY
        )
