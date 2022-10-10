import os
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

        copytree_patch = mock.patch('shutil.copytree')
        # ToDo validate calls in tests
        self.copytree_mock = copytree_patch.start()
        self.addCleanup(copytree_patch.stop)

        # ToDo Verify with tests that link is happening
        path_link_patch = mock.patch('pathlib.Path.symlink_to')
        self.path_link_mock = path_link_patch.start()
        self.addCleanup(path_link_patch.stop)


        client_class_patch = mock.patch('docker.client.from_env')
        self.client_class_mock = client_class_mock = client_class_patch.start()
        self.addCleanup(client_class_patch.stop)

        reglob_patch = mock.patch('tox_in_docker.util.ReGlobPath')
        self.reglob_mock = reglob_patch.start()
        reglob_instance = self.reglob_mock.return_value
        self.addCleanup(reglob_patch.stop)
        reglob_instance.joinpath.configure_mock(return_value=reglob_instance)

        # make reglob yield matches
        reglob_instance.re_glob.configure_mock(return_value=iter(mock.MagicMock() for _i in range(2)))

        # set up some names for easier use
        self.client_mock = client_mock = client_class_mock.return_value
        self.run_mock = run_mock = client_mock.containers.run
        self.create_container_mock = create_mock = client_mock.containers.create
        self.container_from_run_mock = run_mock.return_value
        self.container_from_create_mock = create_mock.return_value


        # setup default successful container run
        self._set_container_status(0)

    def _set_container_status(self, status: int, error: str = None) -> None:
        self.container_from_create_mock.wait.configure_mock(return_value={'StatusCode': status, 'Error': error})
        self.container_from_run_mock.wait.configure_mock(return_value={'StatusCode': status, 'Error': error})

    def test_run_tests_explicit_image(
            self, temporary_directory_mock):
        """
        Test runing tests in a docker image provided by the configuration.
        """

        venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())
        venv_mock.path = '/some/path'
        venv_mock.name = 'mock-venv-pls-ignore'
        tox_in_docker.main.run_tests(venv_mock, image=IMAGE_TAG)

        self.create_container_mock.assert_called_once_with(
            image=IMAGE_TAG,
            volumes={
                temporary_directory_mock().name: {'bind': os.getcwd(), 'mode': 'rw'},
                str(Path().absolute()): {'bind': '/testing-ro', 'mode': 'ro'},
                venv_mock.envconfig.config.toxworkdir: {'bind': '/.tox', 'mode': 'rw'}
            },
            command=['-e', AnyMock],
            user=AnyInt,
            detach=True
        )

        self.container_from_create_mock.start.assert_called_once_with()

        self.container_from_create_mock.attach.assert_called_once_with(
            logs=True, stdout=True, stderr=True, stream=True
        )

    def test_run_tests_auto_image(
            self, temporary_directory_mock):

        with mock.patch('tox_in_docker.util.get_default_image') as get_image_mock:

            venv_mock = mock.Mock(spec=tox.venv.VirtualEnv())
            venv_mock.path = '/a/path/eh'
            venv_mock.name = 'mock-venv-pls-ignore'
            venv_mock.envconfig.in_docker = True
            tox_in_docker.main.run_tests(venv_mock)

            get_image_mock.assert_called_once_with(venv_mock.envconfig.envname)

            # Todo Mock os.getcwd
            self.create_container_mock.assert_called_once_with(
                image=get_image_mock.return_value,
                volumes={
                    temporary_directory_mock().name: {'bind': os.getcwd(), 'mode': 'rw'},
                    str(Path().absolute()): {'bind': '/testing-ro', 'mode': 'ro'},
                    venv_mock.envconfig.config.toxworkdir: {'bind': '/.tox', 'mode': 'rw'}
                },
                command=['-e', venv_mock.envconfig.envname],
                user=AnyInt,
                detach=True
            )

            self.container_from_create_mock.start.assert_called_once_with()

            self.container_from_create_mock.attach.assert_called_once_with(
                logs=True, stdout=True, stderr=True, stream=True
            )
