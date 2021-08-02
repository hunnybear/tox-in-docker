"""
tox_in_docker.util

Utilities for tox_in_docker, I guess
"""

import docker
import re

ENV_IMAGE_XFORMS = {
    # Not sure if it would be overengineering to make this handle both py and pypy
    re.compile(r'^py\d{1,}$'):
        lambda env: f'python:{env[2]}{"." + env[3:] if len(env) > 3 else ""}',
    re.compile('^py$'): lambda env: 'python:latest',
    re.compile('^pypy$'): lambda env: 'pypy:latest',
    re.compile(r'pypy\d{1,}$'):
        lambda env: f'pypy:{env[4]}{("." + env[5:] if len(env) > 5 else "")}',
}


def get_default_image(environment, transforms=None, verify=True):
    """
    Get the default image which should be used for a given environment.
    """

    if transforms is None:
        transforms = ENV_IMAGE_XFORMS

    matched = set()

    for regex, transform in transforms.items():
        if regex.match(environment):
            print('match')
            print(environment)
            print(transform(environment))
            matched.add((regex, transform(environment)))

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
