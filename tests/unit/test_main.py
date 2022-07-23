import unittest
import unittest.mock as mock

import tox

import tox_in_docker.main

ENV_NAME = 'my_env'
IMAGE_TAG = 'my_image:oldest'


@mock.patch('tempfile.TemporaryDirectory')
@mock.patch('docker.client.DockerClient')
class Test_Launch(unittest.TestCase):

    def setUp(self):
        # For some reason was having difficulty with this as a decorator
        self.open_mock = mock.mock_open()

        open_patch = mock.patch('builtins.open', self.open_mock)
        try:
            # will fail on python2
            open_patch.start()
        except ImportError:
            open_patch = mock.patch('__main__.open', self.open_mock)
            open_patch.start()

        self.addCleanup(open_patch.stop)

        chmod_patch = mock.patch('os.chmod')
        chmod_patch.start()
        self.addCleanup(chmod_patch.stop)

    def test_run_tests_explicit_image(
            self,
            client_class_mock,
            temporary_directory_mock):

        client_mock = client_class_mock.return_value

        venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())

        tox_in_docker.main.run_tests(venv_mock, image=IMAGE_TAG)

        client_mock.containers.run.assert_called_once_with(
            image=IMAGE_TAG,
            # might be nice to enforce dict
            volumes=mock.ANY,
            entrypoint=mock.ANY,
            stream=True
        )

    def test_run_tests_auto_image(
            self, client_class_mock,
            temporary_directory_mock):

        with mock.patch('tox_in_docker.util.get_default_image') as get_image_mock:

            venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())
            tox_in_docker.main.run_tests(venv_mock)

            get_image_mock.assert_called_once_with(venv_mock.envconfig.envname)

            client_class_mock.return_value.containers.run.assert_called_once_with(
                ENV_NAME,
                image=get_image_mock.return_value,
                volumes=mock.ANY,
                entrypoint=mock.ANY
            )
