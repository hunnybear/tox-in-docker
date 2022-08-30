"""
tox_in_docker.plugin

Tox plugin hooks
"""

import docker
import os.path
import pluggy
import shutil
import tox
import tox.exception
from tox_in_docker import main
from tox_in_docker import util

hookimpl = pluggy.HookimplMarker("tox")

DEFAULT_DOCKER_IMAGE = 'default'


@hookimpl
def tox_addoption(parser: tox.config.Parser):
    """Add a command line option for later use"""
    parser.add_argument("--no_tox_in_docker", action='store_false', default=None, dest='in_docker',
                        help="disable this plugin")

    parser.add_argument('--in_docker', action='store_true', default=None, dest='always_in_docker')

    parser.add_testenv_attribute(
        name="in_docker",
        type="bool",
        default=False,
        help=' '.join((
            "set `true` to use tox-in-docker if an appropriate Python is not",
            "available locally. Overridden by `always_in_docker`"))
    )

    parser.add_testenv_attribute(
        name='always_in_docker',
        type='bool',
        default=False,
        help=' '.join((
            'set `True` to use tox-in-docker always, even if an appropriate',
            'Python is available locally. Overrides `in_docker`'))
    )

    parser.add_testenv_attribute(
        name="docker_image",
        type="string",
        help=' '.join([
            'A Docker image to run the test/stage in. if `docker_build_dir`',
            'is used, this will be the tag of the created image'])
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


def do_run_in_docker(venv=None, envconfig=None, config=None):
    """
    Return `True` if this test env should be run in a docker container

    `config` is from cli, `envconfig` is from `tox.ini` etc., more or less, I think.
    """

    if envconfig is None:
        if venv is not None:
            envconfig = venv.envconfig

    if config is None:
        if envconfig is not None:
            config = envconfig.config

    if config.option.always_in_docker:
        return True

    elif envconfig is not None and envconfig.always_in_docker:
        return True

    # config.option
    elif (envconfig is not None and envconfig.in_docker) or config.option.in_docker:
        hook = config.interpreters.hook.tox_get_python_executable.name
        plugin = config.pluginmanager.get_plugin('tox-in-docker')
        executable = config.pluginmanager.subset_hook_caller(hook, [plugin])(envconfig=envconfig, skip_tid=True)

        if executable is None:
            return True

    return False


def is_in_docker():
    """ Pretty self-explanatory"""

    return os.path.exists('/.dockerenv')


def _ensure_tox_installed(client, docker_image: str) -> str:

    # Ensure tox in image
    #  - try to run image with --entrypoint tox and --version
    #     + if status != 0, build new image based off of previous image with
    #       tox installed
    try:
        client.containers.run(image=docker_image, entrypoint='tox', command=['--version'])
    except docker.errors.APIError:
        # [re-] build image with tox

        built_image = main.build_testing_image(base=docker_image)
        docker_image = built_image.id

    # TODO: Raise specific exception
    # ensure that built image is set up for tox

    client.containers.run(image=docker_image, command=['--version'])
    return docker_image



@hookimpl
def tox_testenv_create(venv: tox.venv.VirtualEnv, action):
    if not do_run_in_docker(venv=venv):
        return None

    if venv.envconfig.envname.startswith('.'):
        # Not sure if this is too prescriptive
        return None

    # May want to make the pull disable-able


@hookimpl
def tox_get_python_executable(envconfig, skip_tid: bool=False):
    """
    Override default python executable lookup if we're running inside of a
    container

    """

    print(f'getting exe for {envconfig.envname}. skip_tid is {skip_tid}')

    if skip_tid:
        return None

    if not do_run_in_docker(envconfig=envconfig):
        return None
    image = envconfig.docker_image or util.get_default_image(envconfig.envname, default='python:latest')

    if image:
        return shutil.which('python')


@hookimpl
def tox_runtest_post(venv: tox.venv.VirtualEnv):
    # Options (like `config.option` in `tox_configure`) are at
    # `venv.envconfig.config.option`

    if venv.run_image is not None:
        print(f'converting {venv.envconfig.envname} to {venv.run_image}')
        venv.envconfig.envname += ' (in docker)'


@hookimpl
def tox_runtest_pre(venv: tox.venv.VirtualEnv):

    # Set property on virtualenv
    venv.run_image = None

    if not do_run_in_docker(venv=venv):
        return None

    client = docker.client.from_env()

    if venv.envconfig.docker_build_dir:
        if venv.envconfig.docker_image:

            raise tox.exception.ConfigError('cannot specify both docker_image and docker_build_dir in one environment')

        # Build the image
        image, _output = client.images.build(path=venv.envconfig.docker_build_dir)
        docker_image = image.id

    else:
        # use a pulled/available image:

        if venv.envconfig.docker_image is None or venv.envconfig.docker_image.lower() in ['false', 'none']:
            docker_image = util.get_default_image(venv.envconfig.envname)
        elif venv.envconfig.docker_image.lower() == DEFAULT_DOCKER_IMAGE:
            # use `python:latest` if another default cannot be found
            docker_image = util.get_default_image(venv.envconfig.envname, default=True)
        # Implicit else is that docker_image stays the same (it was set to a specific image)

    docker_image = _ensure_tox_installed(client, docker_image)
    venv.envconfig.docker_image = docker_image


@hookimpl
def tox_runtest(venv: tox.venv.VirtualEnv, redirect: bool):
    """
    Args:
        `venv`: The VirtualEnv object for this specific environment
        `redirect` (bool): I have no clue what this does yet

    # ToDo it may be valuable to play with redirection to get realtime streaming
        output from the container
    """

    print(f'{"" if do_run_in_docker(venv=venv) else "Not "}doing run in docker.')

    if is_in_docker():
        print(f"\nAlready in docker\n{'=' * 13}n")
    else:
        print(f"\nNot in docker (yet?)\n{'=' * 13}\n")

    if not do_run_in_docker(venv=venv):
        return None

    docker_image = venv.envconfig.docker_image
    venv.run_image = docker_image
    main.run_tests(venv, docker_image)
    return True
