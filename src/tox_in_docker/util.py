"""
tox_in_docker.util

Utilities for tox_in_docker, I guess
"""

import collections
import re

LATEST = 'python:latest'

Match = collections.namedtuple('Match', ['regex', 'image'])


class NoJythonSupport(ValueError):
    """
    Raise this when someone attempts to run a test for a Jython environment
    """

    def __init__(self, environment_name):
        msg = f'detected environment {environment_name} as jython, which `tox-in-docker` does not support!'
        super().__init__(msg)


ENV_IMAGE_XFORMS = {
    # Not sure if it would be overengineering to make this handle both py and pypy
    re.compile(r'^py\d{1,}$'):
        lambda env: f'python:{env[2]}{"." + env[3:] if len(env) > 3 else ""}',
    re.compile('^py$'): lambda env: 'python:latest',
    re.compile('^pypy$'): lambda env: 'pypy:latest',
    re.compile(r'^pypy\d{1,}$'):
        lambda env: f'pypy:{env[4]}{("." + env[5:] if len(env) > 5 else "")}',
    re.compile('^jy'): NoJythonSupport
}


def get_default_image(envname, transforms=None, verify=True, default=None):
    """
    Get the default image which should be used for a given environment.
    """

    if default is True:
        default = LATEST

    if transforms is None:
        transforms = ENV_IMAGE_XFORMS

    matched = set()

    for regex, transform in transforms.items():
        if regex.match(envname):
            transformed = transform(envname)
            if isinstance(transformed, Exception):
                raise transformed
            matched.add(Match(regex, transformed))

    if len(matched) > 1:
        raise ValueError("\n".join([
            f"Multiple transform matches matched for environment {envname}!",
            "\n\t* ".join([""] + [regex.pattern for regex in zip(*matched)[0]])
        ]))

    elif not matched:
        if default is not None:
            matched.add(Match(None, default))
        else:
            raise ValueError(f"Could not find image to match environment {envname}!")

    return matched.pop().image
