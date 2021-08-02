"""
tox_in_docker.util

Utilities for tox_in_docker, I guess
"""

import docker
import re
import tox


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


def get_default_image(venv: tox.venv.VirtualEnv, transforms=None, verify=True):
    """
    Get the default image which should be used for a given environment.
    """

    if transforms is None:
        transforms = ENV_IMAGE_XFORMS

    matched = set()

    for regex, transform in transforms.items():
        if regex.match(venv.envname):
            print('match')
            matched.add((regex, transform(venv.envname)))

    print(matched)
    print(list(zip(*matched)))

    if len(matched) > 1:
        raise ValueError("\n".join([
            f"Multiple transform matches matched for environment {environment}!",
            "\n\t* ".join([""] + [regex.pattern for regex in zip(*matched)[0]])
        ]))

    elif not matched:
        raise ValueError(f"Could not find image to match environment {environment}!")

    return matched.pop()[1]
