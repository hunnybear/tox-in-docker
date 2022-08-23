import unittest
from unittest import mock

import tox

from tox_in_docker import plugin

from .util import AnyStr


def _get_mocks(count:int) -> list:
    return [mock.Mock() for _ in range(count)]

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


class TestRuntestPre(unittest.TestCase):

    def setUp(self) -> None:
        do_run_in_docker_patch = mock.patch('tox_in_docker.plugin.do_run_in_docker', spec=plugin.do_run_in_docker)
        self.do_run_in_docker_mock = do_run_in_docker_patch.start()
        self.addCleanup(do_run_in_docker_patch.stop)

    def test_skip(self) -> None:
        venv_mock = mock.Mock()
        self.do_run_in_docker_mock.configure_mock(return_value=False)

        self.assertFalse(plugin.tox_runtest_pre(venv_mock))

        # This should also accept a positional argument, that would be a nice
        # addition to mock I think (when given spec, allow flexibility w/r/t kwarg vs arg.
        self.do_run_in_docker_mock.assert_called_once_with(venv=venv_mock)



class TestDoRunInDocker(unittest.TestCase):

    def setUp(self) -> None:
        self.config_mock = mock.Mock(spec=tox.config.Config(*_get_mocks(5)))
        self.envconfig_mock = mock.Mock(spec=tox.config.TestenvConfig('py', self.config_mock, *_get_mocks(2)))
        self.venv_mock = mock.Mock(spec=tox.venv.VirtualEnv(envconfig=self.envconfig_mock))

        self.venv_mock.envconfig = self.envconfig_mock
        self.envconfig_mock.config = self.config_mock


    def test_input_branches(self) -> None:

        self.config_mock.always_in_docker = True

        with self.subTest('venv, neither_config_nor_envconfig'):
            res = plugin.do_run_in_docker(venv=self.venv_mock)
            self.assertTrue(res)

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
