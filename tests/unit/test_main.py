from pathlib import Path
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


        client_class_patch = mock.patch('docker.client.from_env')
        self.client_class_mock = client_class_mock = client_class_patch.start()
        self.addCleanup(client_class_patch.stop)

        # set up some names for easier use
        self.client_mock = client_mock = client_class_mock.return_value
        self.run_mock = run_mock = client_mock.containers.run
        self.container_mock = run_mock.return_value


        # setup default successful container run
        self._set_container_status(0)

    def _set_container_status(self, status: int, error: str = None) -> None:
        self.container_mock.wait.configure_mock(return_value={'StatusCode': status, 'Error': error})

    def test_run_tests_explicit_image(
            self, temporary_directory_mock):
        """
        Test runing tests in a docker image provided by the configuration.
        """

        venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())
        tox_in_docker.main.run_tests(venv_mock, image=IMAGE_TAG)

        self.run_mock.assert_called_once_with(
            image=IMAGE_TAG,
            volumes={
                temporary_directory_mock().__enter__(): {'bind': '/working_dir', 'mode': 'rw'},
                str(Path().absolute()): {'bind': '/testing-ro', 'mode': 'ro'}
            },
            command=['-e', AnyMock],
            stream=True,
            stderr=True,
            stdout=True,
            user=AnyInt,
            remove=True,
            detach=True
        )

    def test_run_tests_auto_image(
            self, temporary_directory_mock):

        with mock.patch('tox_in_docker.util.get_default_image') as get_image_mock:

            venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())
            venv_mock.envconfig.in_docker = True
            tox_in_docker.main.run_tests(venv_mock)

            get_image_mock.assert_called_once_with(venv_mock.envconfig.envname)

            self.run_mock.assert_called_once_with(
                image=get_image_mock.return_value,
                volumes={
                    temporary_directory_mock().__enter__(): {'bind': '/working_dir', 'mode': 'rw'},
                    str(Path().absolute()): {'bind': '/testing-ro', 'mode': 'ro'}
                },
                command=['-e', venv_mock.envconfig.envname],
                stream=True,
                stderr=True,
                stdout=True,
                user=AnyInt,
                remove=True,
                detach=True
            )
