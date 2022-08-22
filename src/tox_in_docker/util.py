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



# These are ordered, the first one to achieve a match will be used
ENV_IMAGE_XFORMS = [
    (re.compile(r'^py(\d*)$'),
        lambda match: f'python:{_get_version_tag(match)}-slim'),
    (re.compile(r'^pypy(\d*)$'),
        lambda match: f'pypy:{_get_version_tag(match)}-slim'),
    (re.compile(r'^(jy.*)$'), NoJythonSupport)
]


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
