import collections
import functools
import unittest
from unittest import mock

import docker
import tox

from tox_in_docker import main, plugin

from .util import AnyStr


def _get_mocks(count:int) -> list:
    return [mock.Mock() for _ in range(count)]

class TestConfiguration(unittest.TestCase):

    def test_add_option(self) -> None:

        parser_mock = mock.Mock(spec=tox.config.Parser())

        res = plugin.tox_addoption(parser_mock)

        parser_mock.add_argument.assert_has_calls([
                mock.call('--in_docker', action='store_true', dest='in_docker', default=None),
                mock.call('--no_tox_in_docker', action='store_false',
                          default=None, dest='in_docker', help=AnyStr),
                mock.call('--always_in_docker', action='store_true', default=None, dest='always_in_docker')
            ],
            any_order=True)

        self.assertIsNone(res)


class TestCase(unittest.TestCase):
    """
    Base test case which sets up some of the environment configuration mocking
    """

    # Todo class constructor or param (or cached?) which makes a mock, runs it through
    # tox_addoption, and scrapes param names so that spec can be updated for venv opts

    @classmethod
    def _get_envconfig_spec_properties(cls) -> set:
        parser_mock = mock.Mock()

        plugin.tox_addoption(parser_mock)

        properties = set(call.kwargs['name'] for call in parser_mock.add_testenv_attribute.call_args_list)
        properties.update(call.kwargs.get('dest', call.args[0].strip('-').replace('-', '_')) for call in parser_mock.add_argument.call_args_list)

        return properties

    def setUp(self) -> None:
        self.config_mock = mock.Mock(spec=tox.config.Config(*_get_mocks(5)))
        self.envconfig_mock = mock.Mock(
            spec=tox.config.TestenvConfig('py', self.config_mock, *_get_mocks(2)))
        # update mock with properties so spec is happy
        self.envconfig_mock.configure_mock(**dict((prop, mock.MagicMock()) for prop in self._get_envconfig_spec_properties()))

        self.venv_mock = mock.Mock(spec=tox.venv.VirtualEnv(envconfig=self.envconfig_mock))

        self.venv_mock.envconfig = self.envconfig_mock
        self.envconfig_mock.config = self.config_mock

        # Pre configure some values
        self._set_build_dir(None)


    def _set_build_dir(self, build_dir: str) -> None:

        self.envconfig_mock.docker_build_dir = build_dir


class TestRuntestPre(TestCase):

    def setUp(self) -> None:
        super().setUp()

        do_run_in_docker_patch = mock.patch('tox_in_docker.plugin.do_run_in_docker', spec=plugin.do_run_in_docker)
        self.do_run_in_docker_mock = do_run_in_docker_patch.start()
        self.addCleanup(do_run_in_docker_patch.stop)

        client_constructor_patch = mock.patch('docker.client.from_env')
        self.client_constructor_mock = client_constructor_patch.start()
        self.addCleanup(client_constructor_patch.stop)

        self.client_mock = self.client_constructor_mock.return_value

        self.run_mock = self.client_mock.containers.run
        self.build_mock = self.client_mock.images.build

        self.built_image_mock = mock.Mock()
        self.build_mock.configure_mock(return_value=(self.built_image_mock, mock.Mock()))

    def test_skip(self) -> None:
        self.do_run_in_docker_mock.configure_mock(return_value=False)

        self.assertIsNone(plugin.tox_runtest_pre(self.venv_mock))

        # This should also accept a positional argument, that would be a nice
        # addition to mock I think (when given spec, allow flexibility w/r/t kwarg vs arg.
        self.do_run_in_docker_mock.assert_called_once_with(venv=self.venv_mock)

    @mock.patch('os.getcwd')
    @mock.patch('socket.gethostname')
    @mock.patch('tox_in_docker.util.get_default_image')
    @mock.patch('tox_in_docker.main.build_testing_image',
                spec=main.build_testing_image)
    def test_build_from_build_dir(
        self, build_image_mock: mock.Mock, get_image_mock:mock.Mock,
        get_hostname_mock, getcwd_mock) -> None:

        build_dir = '/test/dir/please/ignore'
        cwd = 'ignore'
        getcwd_mock.configure_mock(return_value=cwd)

        self._set_build_dir(build_dir)

        self.do_run_in_docker_mock.configure_mock(return_value=True)
        self.envconfig_mock.docker_image = None


        plugin.tox_runtest_pre(self.venv_mock)
        self.build_mock.assert_called_once_with(
            buildargs={'BASE': get_image_mock.return_value},
            path=build_dir,
            tag=f'tid-{get_hostname_mock.return_value.lower()}-{cwd}:latest'
        )

        # ToDo reset and check with docker image set




class TestDocker(TestCase):

    @mock.patch('tox_in_docker.main.build_testing_image')
    def test_ensure_installed(self, build_image_mock) -> None:
        try:
            mock_client = mock.Mock(spec=docker.client.DockerClient())

        # if docker isn't running/available, this will occur
        except docker.errors.DockerException:
            # ToDo spec this when cannot connect to docker server
            mock_client = mock.Mock()

        docker_image = 'vogsphere:42'

        with self.subTest('image needs tox'):
            mock_client.containers.run.configure_mock(
                side_effect=((docker.errors.APIError(
                    'some message I guess'), True)))

            res = plugin._ensure_tox_installed(mock_client, docker_image)
            self.assertIs(res, build_image_mock.return_value.tags[0])

        mock_client.reset_mock()
        with self.subTest('image already has tox'):
            mock_client.containers.run.reset_mock()
            mock_client.containers.run.configure_mock(return_value=True, side_effect=None)

            res = plugin._ensure_tox_installed(mock_client, docker_image)
            self.assertEqual(res, docker_image)

class TestDoRunInDocker(TestCase):

    def test_in_docker_and_always_in_docker(self):
        """
        """

        hook_caller_mock = self.config_mock.pluginmanager.subset_hook_caller.return_value


        Case = collections.namedtuple('Case', [
            'py_exe', 'cli_always', 'cli_in_d', 'ini_always', 'ini_in_d', 'result'])
        Case = functools.partial(Case, cli_always=None, cli_in_d=None, ini_always=None, ini_in_d=None)

        cases = [
            # overrides disabled (explicit false) in ini file
            Case(py_exe= True, cli_always=True, cli_in_d=False, ini_always=False, ini_in_d=False, result=True),
            Case(py_exe=True, cli_always=True, cli_in_d=True, ini_always=False, ini_in_d=False, result=True),
            Case(py_exe=True, cli_always=True, ini_always=False, ini_in_d=False, result=True),
            Case(py_exe=True, cli_always=True, ini_in_d=False, result=True),
            Case(py_exe=True, cli_always=True, result=True),
            # always in docker in the config file
            Case(py_exe=True, ini_always=True, ini_in_d=False, result=True),
            Case(py_exe=True, ini_always=True, ini_in_d=True, result=True),
            Case(py_exe=True, ini_always=True, ini_in_d=None, result=True),
            # CLI, not always in docker
            # ## python locally exists
            Case(py_exe=True, cli_in_d=True, result=False),
            Case(py_exe=True, cli_in_d=False, result=False),
            Case(py_exe=True, cli_in_d=True, ini_in_d=False, result=False),
            # ### Check that ini always still overrides.
            Case(py_exe=True, cli_in_d=True, ini_always=True, result=True),
            # ## Python does not locally exist
            Case(py_exe=False, cli_in_d=True, result=True),
            Case(py_exe=False, cli_in_d=False, ini_in_d=True, result=True),
            Case(py_exe=False, ini_in_d=True, result=True)
        ]

        for case in cases:
            with self.subTest(Case):
                self.config_mock.option.in_docker = case.cli_in_d
                self.envconfig_mock.in_docker = case.ini_in_d

                self.config_mock.option.always_in_docker = case.cli_always
                self.envconfig_mock.always_in_docker = case.ini_always

                if case.py_exe:
                    hook_caller_mock.configure_mock(return_value='/this/should/work/eh/python3')
                else:
                    hook_caller_mock.configure_mock(return_value=None)

                res = plugin.do_run_in_docker(config=self.config_mock, envconfig=self.envconfig_mock)
                self.assertEqual(res, case.result)


    def test_input_branches(self) -> None:

        self.config_mock.always_in_docker = True

        with self.subTest('venv, neither_config_nor_envconfig'):
            res = plugin.do_run_in_docker(venv=self.venv_mock)
            self.assertTrue(res)

        with self.subTest('envconfig, only'):
            res = plugin.do_run_in_docker(envconfig=self.envconfig_mock)

        with self.subTest('venv, envconfig, config'):
            res = plugin.do_run_in_docker(venv=self.venv_mock,
                                    envconfig=self.envconfig_mock)

            self.assertTrue(res)

        with self.subTest('venv, envconfig, and config'):
            res = plugin.do_run_in_docker(venv=self.venv_mock,
                                    envconfig=self.envconfig_mock,
                                    config=self.config_mock)
            self.assertTrue(res)

        with self.subTest('no venv with config'):
            res = plugin.do_run_in_docker(config=self.config_mock)
            self.assertTrue(res)


    def test_config_use(self) -> None:
        pypath = '/usr/bin/python3'
        for always_in_docker, in_docker, found_exe, expected in [
                (True, False, pypath, True),  # Both in docker and found exe should be irrelevant here
                (True, True, pypath, True),  # Even though they should be irrelevant, checking this at least
                (False, True, pypath, False),  # When in docker, and executable is found, don't run in docker
                (False, True, None, True), # When in docker, and executable not found, run in docker
                (False, False, None, False)]:  # When neither always in docker nor in docker, never use docker

            with self.subTest(always_in_docker=always_in_docker,
                              in_docker=in_docker,
                              found_exe=found_exe,
                              expected=expected):
                self.config_mock.reset_mock()
                self.config_mock.option.always_in_docker = always_in_docker
                self.config_mock.option.in_docker = in_docker

                self.config_mock.pluginmanager.subset_hook_caller.return_value.return_value = found_exe
                res = plugin.do_run_in_docker(config=self.config_mock)

                self.assertEqual(res, expected)
