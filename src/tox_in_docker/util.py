"""
tox_in_docker.util

Utilities for tox_in_docker, I guess
"""

import collections
from collections.abc import Iterator, Callable, Sequence, Mapping
from dataclasses import dataclass
import functools
import os
import pathlib
import re
import signal
import sys

LATEST = 'python:latest'

Match = collections.namedtuple('Match', ['regex', 'image'])
TerminationCleanup = collections.namedtuple('Cleanup', ['hook', 'pass_self', 'args', 'kwargs'])

@dataclass
class TerminationCleanup:
    """
    Class for tracking cleanup of a graceful terminator
    """

    handler: Callable
    pass_self: bool
    pass_frame: bool
    args: Sequence
    kwargs: Mapping

    def __iter__(self):

        yield self.handler
        yield self.pass_self
        yield self.pass_frame
        yield self.args
        yield self.kwargs


# pathlib.Path() gets one of several classes depending on the OS, this gets us
# our desired base class
class ReGlobPath(pathlib.Path().__class__):
    """
    Pathlib Path subclass which adds a method for globbing by regex

    ToDo: Fix type hinting for pattern to include compiled regex
    """
    def re_glob(self, pattern: str, yield_child: bool = True, yield_match: bool = False) -> Iterator:
        """
        yield the direct children of this path which match a regex
        """

        if not any((yield_match, yield_child)):
            raise ValueError('re_glob requires either `yield_child` or `yield_match` to be truthy.')

        for child in self.iterdir():
            match = re.match(pattern, child.name)
            if match and yield_child and yield_match:
                yield (child, match)
            elif match and yield_child:
                yield child
            # Could be done with `else`, but explicit is better than implicit
            elif match and yield_match:
                yield match
            # part of me wants to throw an assertion on `else`, but the other
            # wolf considers this overkill and/or overengineering.


class NoJythonSupport(ValueError):
    """
    Raise this when someone attempts to run a test for a Jython environment
    """

    def __init__(self, environment_name):
        msg = f'detected environment {environment_name} as jython, which `tox-in-docker` does not support!'
        super().__init__(msg)


# These are ordered, the first one to achieve a match will be used
ENV_IMAGE_XFORMS = [
    (re.compile(r'^py(\d*)$'),
        lambda match: f'python:{_get_version_tag(match)}-slim'),
    (re.compile(r'^pypy(\d*)$'),
        lambda match: f'pypy:{_get_version_tag(match)}-slim'),
    (re.compile(r'^(jy.*)$'), NoJythonSupport)
]


def is_in_docker():
    """ Pretty self-explanatory"""

    return os.path.exists('/.dockerenv')

def _get_version_tag(env_version: str):
    """
    Get the docker tag to use given the python environment name
    """

    if not env_version:
        return 'latest'

    elif not env_version.isdigit():
        # ToDo something more specific
        raise ValueError(f'env version must be "latest" or a digit')

    # Tox environments for Python 3.10 can be expressed py10, assuming the
    # pattern continues for other Python 3.1xs
    elif env_version.startswith('1'):
        return f'3.{env_version}'

    elif len(env_version) == 1:
        return env_version

    else:
        # version contains major and minor versions
        return f'{env_version[0]}.{env_version[1:]}'



def get_default_image(envname, transforms=None, verify=True, default=None):
    """
    Get the default image which should be used for a given environment.
    """

    if default is True:
        default = LATEST

    if transforms is None:
        transforms = ENV_IMAGE_XFORMS

    for regex, transform in transforms:
        match = regex.match(envname)
        if match is not None:
            transformed = transform(match.groups()[0])
            if isinstance(transformed, Exception):
                raise transformed
            return transformed

    if default is None:
        raise ValueError(f"Could not find image to match environment {envname}!")

    return default


class HandleInterruptions:
    """
    This class

    It's ME, The Interrup--- catches SIGINT and
    """

    def __init__(self, exit_code: int = None, cleanup_on_exit: bool = False, handling: bool = True):
        self.handling = handling
        self.exit_code = exit_code
        self.cleanup_on_exit = cleanup_on_exit
        self.prev_int_handler = signal.signal(signal.SIGINT, self._gracefully_interrupt)
        self._cleanup = []

    def add_cleanup(
            self, handler,
            *args,
            pass_self: bool = False, pass_frame: bool = False,
            **kwargs) -> TerminationCleanup:

        cleanup_spec = TerminationCleanup(
            handler=handler, pass_self=pass_self, pass_frame=pass_frame, args=args, kwargs=kwargs)
        self._cleanup.append(cleanup_spec)

        return cleanup_spec

    def _gracefully_interrupt(self, sig: int, frame) -> None:
        """

        Notes:
            * I'm not certain if I want this to catch and re-raise exceptions,
                or some other similar Magick
        """

        for this_handler, pass_self, pass_frame, posargs, kwargs in self._cleanup:
            if pass_self and pass_frame:
                posargs = tuple([self, frame] + list(posargs))
            elif pass_self:
                posargs = tuple([self] + list(posargs))
            elif pass_frame:
                posargs = tuple([frame] + list(posargs))
            this_handler(*posargs, **kwargs)

        self.handling = False

    def __enter__(self):
        self.handling = True
        return self

    def __exit__(self, *args, **kwargs):
        # ToDo correct args

        if self.handling and self.cleanup_on_exit:
            self._gracefully_interrupt(None, None)

        signal.signal(signal.SIGINT, self.prev_int_handler)
        # ToDo perhaps resend SIGINT?

        if self.exit_code is not None:
            sys.exit(self.exit_code)
