"""
Tests for the utilities module of tox-in-docker
"""


from collections.abc import Iterator, Callable, Sequence, Mapping
from dataclasses import dataclass
import signal
import unittest
from unittest import mock

from tox_in_docker import util


class TestGetDefaultImages(unittest.TestCase):
    BASES = [('py', 'python'), ('pypy', 'pypy')]

    def test_latest(self):

        for env, image_base in self.BASES:
            with self.subTest(env=env, image_base=image_base):
                res = util.get_default_image(env)
                self.assertEqual(res, f'{image_base}:latest-slim')

    def test_major(self):
        for env, image_base in self.BASES:
            for version in range(2, 4):
                print(version, str(version))
                this_env = f'{env}{str(version)}'
                with self.subTest(env=env, this_env=this_env, image_base=image_base):
                    res = util.get_default_image(this_env)
                    print([res, image_base, version])
                    self.assertEqual(res, f'{image_base}:{version}-slim')

    def test_minor(self):
        for env, image_base in self.BASES:
            for maj_version in [2, 3]:
                for min_version in [1, 2, 12]:
                    this_env = f'{env}{maj_version}{min_version}'
                    with self.subTest(env=env, this_env=this_env, min_version=min_version, maj_version=maj_version):
                        res = util.get_default_image(this_env)
                        self.assertEqual(res, f'{image_base}:{maj_version}.{min_version}-slim')
        # I'm not sure if other pythons are effected, but at least py 3.10
        # environment can be `py10`
        with self.subTest('py', this_env='py10', min_version=10, maj_version=3):
            res = util.get_default_image('py10')
            self.assertEqual(res, 'python:3.10-slim')
        with self.subTest('py', this_env='py13', min_version=13, maj_version=3):
            res = util.get_default_image('py13')
            self.assertEqual(res, 'python:3.13-slim')

    def test_jython_raises_exception(self):
        for jython in ['jy', 'jython', 'jy27', 'jy2', 'jy3', 'jy39', 'jy10']:
            with self.assertRaises(util.NoJythonSupport):
                util.get_default_image(jython)


class TestInterruptionHandler(unittest.TestCase):

    @dataclass
    class CleanupCase:
        pass_self: bool = None
        pass_frame: bool = None
        args: Sequence = None
        kwargs: Mapping = None

        def __repr__(self):
            expected_args = self.get_expected_args('a handler', 'a frame')
            expected_kwargs = self.get_expected_kwargs('a handler', 'a frame')
            return f'{super().__repr__()[:-1]} pass_self: {self.pass_self} pass_frame: {self.pass_frame}>\n\t{self.get_args()}  -->  {expected_args}\n\t{self.get_kwargs()}  -->  {expected_kwargs}'

        def get_args(self) -> tuple:
            if self.args:
                return tuple(self.args)

            return tuple()

        def get_kwargs(self) -> dict:
            """
            Get the kwargs used to call the handler's `.add_cleanup()`
            """

            kwargs = dict(self.kwargs) if self.kwargs else {}
            kwargs.update(
                {
                    'pass_self': self.pass_self,
                    'pass_frame': self.pass_frame
                }
            )

            return kwargs

        def get_expected_call(self, handler: mock.Mock, frame: mock.Mock) -> tuple:
            return (
                self.get_expected_args(handler, frame),
                self.get_expected_kwargs(handler, frame))

        def get_expected_args(self, handler: mock.Mock, frame: mock.Mock) -> tuple:
            expected = []
            if self.pass_self:
                expected.append(handler)
            if self.pass_frame:
                expected.append(frame)

            if self.args:
                expected.extend(self.args)

            return tuple(expected)

        def get_expected_kwargs(self, handler: mock.Mock, frame: mock.Mock) -> dict:
            # return a copy, as the original is mutable.
            return dict(self.kwargs) if self.kwargs else {}


    def setUp(self) -> None:

        signal_patch = mock.patch('signal.signal')
        self.signal_mock = signal_patch.start()
        self.addCleanup(signal_patch.stop)

    def test_handler_sig(self) -> None:

        handler = util.HandleInterruptions()

        self.signal_mock.assert_called_once_with(signal.SIGINT, handler._gracefully_interrupt)

    def test_context_manager(self) -> None:

        with util.HandleInterruptions() as handler:
            self.signal_mock.assert_called_once_with(signal.SIGINT, handler._gracefully_interrupt)
            self.signal_mock.reset_mock()

        self.signal_mock.assert_called_once_with(signal.SIGINT, handler.prev_int_handler)

    def test_handler_multiple_cleanups(self) -> None:
        """
        Ensure that multiple cleanups can be added to the handler, and that they are all called
        """


    def test_handler_cleanups(self) -> None:
        kwarg_a, kwarg_b, arg1, arg2 = (mock.Mock(name=name) for name in ['kwarg: a', 'kwarg:b', 'arg:1', 'arg:2'])
        mock_args = (arg1, arg2)
        mock_kwargs = {'a': kwarg_a, 'b': kwarg_b}

        # I'm always of two minds when deciding whether to automatically
        # generate cases like this, or manually define them.
        cases = [
            # pass neither self nor frame
            self.CleanupCase(pass_self=False, pass_frame=False, args=mock_args, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=False, pass_frame=False, args=mock_args),
            self.CleanupCase(pass_self=False, pass_frame=False, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=False, pass_frame=False),
            # pass self, not frame
            self.CleanupCase(pass_self=True, pass_frame=False, args=mock_args, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=True, pass_frame=False, args=mock_args),
            self.CleanupCase(pass_self=True, pass_frame=False, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=True, pass_frame=False),
            # Pass frame, not self
            self.CleanupCase(pass_self=False, pass_frame=True, args=mock_args, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=False, pass_frame=True, args=mock_args),
            self.CleanupCase(pass_self=False, pass_frame=True, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=False, pass_frame=True),
            # Pass both self and frame
            self.CleanupCase(pass_self=True, pass_frame=True, args=mock_args, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=True, pass_frame=True, args=mock_args),
            self.CleanupCase(pass_self=True, pass_frame=True, kwargs=mock_kwargs),
            self.CleanupCase(pass_self=True, pass_frame=True),
        ]

        interruption_handler = util.HandleInterruptions()

        signal_int_mock = mock.Mock(spec=1)
        frame_mock = mock.Mock()

        for case in cases:
            cleanup = mock.Mock()
            expected_args, expected_kwargs = case.get_expected_call(interruption_handler, frame_mock)

            with self.subTest(case=case):
                interruption_handler.add_cleanup(cleanup, *case.get_args(), **case.get_kwargs())
                interruption_handler._gracefully_interrupt(signal_int_mock, frame_mock)

                self.assertFalse(interruption_handler.handling)
                cleanup.assert_called_once_with(
                    *expected_args,
                    **expected_kwargs)
