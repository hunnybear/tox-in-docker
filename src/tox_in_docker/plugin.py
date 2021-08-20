
import docker
import functools
import os.path
import pdb
import pluggy
import shutil
import tox
import tox.exception
from tox_in_docker import main
from tox_in_docker import util

hookimpl = pluggy.HookimplMarker("tox")

DEFAULT_DOCKER_IMAGE = 'default'

def run_in_docker_only(fn):

    @functools.wraps(fn)
    def decorated(*args, venv=None, envconfig=None, config=None, **kwargs):
        if not args:

            defined_kwargs = dict(
                (k, v) for k, v in [
                    ('venv', venv), ('envconfig', envconfig), ('config', config)
                ] if v is not None
            )

            if not do_run_in_docker(defined_kwargs.get('venv') or defined_kwargs.get('envconfig') or defined_kwargs.get('config') or args[0]):
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

    # ToDo: make the below docker image things mutually exclusive

    parser.add_testenv_attribute(
        name="docker_image",
        type="string",
        help="A Docker image to run the test/stage in"
    )

    parser.add_testenv_attribute(
        name="docker_build_dir",
        type="string",
        help="A Dockerfile from which to build the test container")

    parser.add_testenv_attribute(
        name="cleanup_built_container",
        type="bool",
        help="if True, remove the newly built container after running the test",
        default=False)

    parser.add_testenv_attribute(
        name='pdb',
        type='bool',
        help='Set this to True if you wish to break into PDB for any uncaught exceptions.',
        default=False)

def do_run_in_docker(venv=None, envconfig=None, config=None):
    """
    Return `True` if this test env should be run in a docker container
    """

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
    """ Pretty self-explanatory"""

    return os.path.exists('/.dockerenv')


@hookimpl
def tox_testenv_create(venv: tox.venv.VirtualEnv, action):
    if not do_run_in_docker(venv=venv):
        return None

    if venv.envconfig.envname.startswith('.'):
        # Not sure if this is too prescriptive
        return None

    # May want to make the pull disable-able


@hookimpl
def tox_get_python_executable(envconfig):
    """
    Override default python executable lookup if we're running inside of a
    container

    """

    if not do_run_in_docker(envconfig=envconfig):
        return None
    image = envconfig.docker_image or util.get_default_image(envconfig.envname, default='python:latest')

    if image:
        return shutil.which('python')


@hookimpl
def tox_runtest_post(venv: tox.venv.VirtualEnv):
    # Options (like `config.option` in `tox_configure`) are at
    # `venv.envconfig.config.option`

    pass


@hookimpl
def tox_runtest_pre(venv: tox.venv.VirtualEnv):

    if not do_run_in_docker(venv=venv):
        return None

    docker_image_conversions = {'false': False, 'none': None}

    if venv.envconfig.docker_image.lower() in docker_image_conversions.keys():
        venv.envconfig.docker_image = next(
            res for inval, res in docker_image_conversions.items() if
            venv.envconfig.docker_image.lower() == inval)

    if venv.envconfig.docker_build_dir:
        if venv.envconfig.docker_image:

            raise tox.exception.ConfigError('cannot specify both docker_image and docker_build_dir in one environment')

        # Build the image
        client = docker.client.DockerClient()
        image, _output = client.images.build(path=venv.envconfig.docker_build_dir)
        venv.envconfig.docker_image = image.id

    # Want to always do the usual. explicit is better than implicit
    return None


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

    if not do_run_in_docker(venv=venv):
        return None

    docker_image = venv.envconfig.docker_image

    if docker_image == DEFAULT_DOCKER_IMAGE:
        # use `python:latest` if another default cannot be found
        docker_image = util.get_default_image(venv.envconfig.envname, default=True)
    elif docker_image is None:
        docker_image = util.get_default_image(venv.envconfig.envname)
    # Implicit else is that docker_image stays the same (it was set to a specific image)

    if venv.envconfig.pdb:
        debug_catch = Exception
    else:
        debug_catch = tuple()

    try:
        main.run_tests(venv, image=docker_image)
    except debug_catch:
        pdb.post_mortem()
    return True
