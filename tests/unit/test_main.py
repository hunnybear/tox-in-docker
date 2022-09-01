import unittest
import unittest.mock as mock

import tox

import tox_in_docker.main

from .util import AnyDict, AnyInt, AnyList, AnyMock

ENV_NAME = 'my_env'
IMAGE_TAG = 'my_image:oldest'


class CommandMatcher(list):
    def __init__(self, mock, *args, **kwargs):
        self.mock = mock
        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, list):
            return False
        if self.mock is mock.ANY:
            return all(isinstance(el, str) or isinstance(el, mock.Mock) for el in other)

        return all(isinstance(el, str) or el is self.mock for el in other)


@mock.patch('tempfile.TemporaryDirectory')
@mock.patch('docker.client.from_env')
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
            volumes=AnyDict,
            command=['-e', AnyMock],
            stream=True,
            user=AnyInt
        )

    def test_run_tests_auto_image(
            self, client_class_mock,
            temporary_directory_mock):

        with mock.patch('tox_in_docker.util.get_default_image') as get_image_mock:

            venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())
            venv_mock.envconfig.in_docker = True
            tox_in_docker.main.run_tests(venv_mock)

            get_image_mock.assert_called_once_with(venv_mock.envconfig.envname)

            client_class_mock.return_value.containers.run.assert_called_once_with(
                image=get_image_mock.return_value,
                volumes=AnyDict,
                command=['-e', venv_mock.envconfig.envname],
                stream=True,
                user=AnyInt
            )
