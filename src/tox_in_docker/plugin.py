
import functools
import os.path
import pluggy
import shutil
import tox
import tox.exception
from tox_in_docker import main
from tox_in_docker import util

hookimpl = pluggy.HookimplMarker("tox")

DEFAULT_DOCKER_IMAGE= 'default'

def run_in_docker_only(fn):

    @functools.wraps(fn)
    def decorated(*args, venv=None, envconfig=None, config=None, **kwargs):
        if not args:

            defined_kwargs = dict(
                (k, v) for k, v in [
                    ('venv', venv), ('envconfig', envconfig), ('config', config)
                ] if v is not None
            )

            if not run_in_docker(defined_kwargs.get('venv') or defined_kwargs.get('envconfig') or defined_kwargs.get('config') or args[0]):
                return None

            if venv is not None:
                kwargs['venv'] = venv
            if envconfig is not None:
                kwargs['envconfig'] = envconfig
            if config is not None:
                kwargs['config'] = config

        return fn(*args, **kwargs)
    return decorated


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

#    parser.add_testenv_attribute(
#        name="docker_builds")


def run_in_docker(venv=None, envconfig=None, config=None):

    if envconfig is None:
        if venv is not None:
            envconfig = venv.envconfig

    if config is None:
        if envconfig is not None:
            config = envconfig.config

    assert envconfig is not None or config is not None or venv is not None

    # This will only be false when `--no_tox_in_docker` is provided
    if not config.option.in_docker:
        return False

    if envconfig is not None and envconfig.in_docker:
        return True

    return False


def is_in_docker():
    return os.path.exists('/.dockerenv')


@hookimpl
def tox_configure(config: tox.config.Config):
    """Access your option during configuration"""
    # verbosity0("flag magic is: {}".format(config.option.magic))
    if not run_in_docker(config=config):
        return None
    return None


@hookimpl
def tox_testenv_create(venv: tox.venv.VirtualEnv, action):
    if not run_in_docker(venv=venv):
        return None
    if venv.envconfig.envname.startswith('.'):
        # Not sure if this is too prescriptive
        return None

    # May want to make the pull disable-able


@hookimpl
def tox_get_python_executable(envconfig):
    if not run_in_docker(envconfig=envconfig):
        return None
    image = envconfig.docker_image or util.get_default_image(envconfig.envname, default='python:latest')

    if image:
        return shutil.which('python')
        return image


@hookimpl
def tox_runtest_post(venv: tox.venv.VirtualEnv):
    # Options (like `config.option` in `tox_configure`) are at
    # `venv.envconfig.config.option`

    pass


@hookimpl
def tox_runtest(venv: tox.venv.VirtualEnv, redirect: bool):
    """
    Args:
        `venv`:
        `redirect` (bool): I have no clue what this does yet
    """

    if is_in_docker():
        print("\nrunning test in docker!\n====================\n")
        raise ValueError('foo')
    else:
        print("\nNot in docker (yet?)\n============================\n")

    if not run_in_docker(venv=venv):
        return None

    docker_image = venv.envconfig.docker_image

    if docker_image == DEFAULT_DOCKER_IMAGE:
        # use `python:latest` if another default cannot be found
        docker_image = util.get_default_image(venv.envconfig.envname, default=True)
    elif docker_image is None:
        docker_image = util.get_default_image(venv.envconfig.envname)
    # Implicit else is that docker_image stays the same (it was set to a specific image)

    main.run_tests(venv.envconfig.envname, docker_image)
    return True
