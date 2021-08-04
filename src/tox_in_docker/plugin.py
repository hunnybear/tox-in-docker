import argparse
import functools
import pluggy
import tox
import tox.exception
from tox_in_docker import main
from tox_in_docker import util

hookimpl = pluggy.HookimplMarker("tox")


@hookimpl
def tox_addoption(parser: tox.config.Parser):
    """Add a command line option for later use"""
    parser.add_argument("--no_tox_in_docker", action='store_false', dest='in_docker',
                        help="disable this plugin")

    parser.add_testenv_attribute(
        name="in_docker",
        type="bool",
        help="set `true` to use tox-in-docker"
    )

    parser.add_testenv_attribute(
        name="docker_image",
        type="string",
        help="A Docker image to run the test/stage in"
    )



def _skip_this_perhaps(venv):
    if not venv.envconfig.config.option.in_docker:
        return True

    if not venv.envconfig.in_docker:
        return True


@hookimpl
def tox_configure(config: tox.config.Config):
    """Access your option during configuration"""
    # verbosity0("flag magic is: {}".format(config.option.magic))

    if not config.option.in_docker:
        return None

    # TODO
    pass


@hookimpl
def tox_testenv_create(venv: tox.venv.VirtualEnv, action):

    if _skip_this_perhaps(venv):
        return None

    if venv.envconfig.envname.startswith('.'):
        # Not sure if this is too prescriptive
        return None


@hookimpl
def tox_runtest_post(venv: tox.venv.VirtualEnv):
    # Options (like `config.option` in `tox_configure`) are at
    # `venv.envconfig.config.option`

    if _skip_this_perhaps(venv):
        return None

    pass


@hookimpl
def tox_runtest(venv: tox.venv.VirtualEnv, redirect: bool):
    """
    Args:
        `venv`:
        `redirect` (bool): I have no clue what this does yet
    """

    if _skip_this_perhaps(venv):
        return None
    return True
