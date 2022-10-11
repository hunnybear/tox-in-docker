"""
tox_in_docker.plugin

Tox plugin hooks
"""
import logging
import pathlib
import os
import os.path
import shutil

import docker
from pathlib import Path
import pluggy
import socket
import toml
import tox
import tox.exception

from tox_in_docker import main
from tox_in_docker import util

hookimpl = pluggy.HookimplMarker("tox")

DEFAULT_DOCKER_IMAGE = 'default'

USER_CONF_FILE = pathlib.Path().home().joinpath(
    '.config', 'tox', 'tox-in-docker.toml')


def get_base_image(venv):

    if venv.envconfig.docker_image is None or venv.envconfig.docker_image.lower() in ['false', 'none']:
        return util.get_default_image(venv.envconfig.envname)
    elif venv.envconfig.docker_image.lower() == DEFAULT_DOCKER_IMAGE:
        # use `python:latest` if another default cannot be found
        return util.get_default_image(venv.envconfig.envname, default=True)
    else:
        return venv.envconfig.docker_image

@hookimpl
def tox_addoption(parser: tox.config.Parser):

    # Use defaults from the user configuration
    if USER_CONF_FILE.is_file():
        try:
            user_config = toml.loads(USER_CONF_FILE.read_text())
        except toml.decoder.TomlDecodeError:
            # ToDo give a warning
            user_config = {}
    else:
        user_config = {}

    in_docker_default = user_config.get('global', {}).get('in_docker')
    always_default = user_config.get('global', {}).get('always_in_docker')

    tox.reporter.info(f'Tox in docker user defaults: {user_config.get("global")}')

    parser.add_argument("--no_tox_in_docker", action='store_false', default=in_docker_default, dest='in_docker',
                        help="disable this plugin")

    parser.add_argument('--in_docker', action='store_true', default=in_docker_default, dest='in_docker')
    parser.add_argument('--always_in_docker', action='store_true', default=always_default, dest='always_in_docker')
    parser.add_testenv_attribute(
        name="in_docker",
        type="bool",
        default=in_docker_default or False,
        help=' '.join((
            "set `true` to use tox-in-docker if an appropriate Python is not",
            "available locally. Overridden by `always_in_docker`"))
    )

    parser.add_testenv_attribute(
        name='always_in_docker',
        type='bool',
        default=always_default or False,
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
        help="A directory containing a Dockerfile from which to build the test container"
    )

    parser.add_testenv_attribute(
        name="docker_build_base_arg",
        type="string",
        help="the name of the build arg in your dockerfile which accepts the base image. Requires docker_build_dir",
        default=None)

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
        tox.reporter.info('Tox in docker reason: option.always_in_docker (CLI) is True-y')
        return True

    elif envconfig is not None and envconfig.always_in_docker:
        tox.reporter.info('Tox in docker reason: envconfig.always_in_docker (ini or toml file) is True-y')
        return True

    # config.option
    elif (envconfig is not None and envconfig.in_docker) or config.option.in_docker:
        hook = config.interpreters.hook.tox_get_python_executable.name
        plugin = config.pluginmanager.get_plugin('tox-in-docker')
        executable = config.pluginmanager.subset_hook_caller(hook, [plugin])(envconfig=envconfig, skip_tid=True)

        if executable is None:
            return True

    return False


def _ensure_tox_installed(client, docker_image: str) -> str:
    """
    Ensure tox in image
     - try to run image with --entrypoint tox and --version
        + if status != 0, build new image based off of previous image with
          tox installed
    """

    try:
        client.containers.run(image=docker_image, entrypoint='tox', command=['--version'])
    except docker.errors.APIError:
        # [re-] build image with tox

        built_image = main.build_testing_image(base=docker_image)
        docker_image = built_image.tags[0] if built_image.tags else built_image.id

    # TODO: Raise specific exception
    # ensure that built image is set up for tox

    client.containers.run(image=docker_image, command=['--version'], remove=True)
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

    if skip_tid:
        return None

    if not do_run_in_docker(envconfig=envconfig):
        return None
    image = envconfig.docker_image or util.get_default_image(envconfig.envname, default='python:latest')

    if image:
        envconfig.basepython = f'{envconfig.envname} (in docker)'
        return shutil.which('python')


@hookimpl
def tox_runtest_post(venv: tox.venv.VirtualEnv):
    # Options (like `config.option` in `tox_configure`) are at
    # `venv.envconfig.config.option`

    if venv.run_image is not None:
        # Add (in docker) to the env name for display in results
        venv.envconfig.envname += ' (in docker)'


@hookimpl
def tox_runtest_pre(venv: tox.venv.VirtualEnv):

    # Set property on virtualenv
    venv.run_image = None

    if not do_run_in_docker(venv=venv):
        return None

    #

    client = docker.client.from_env()

    if venv.envconfig.docker_build_dir:
        docker_build_dir = venv.envconfig.docker_build_dir

        # ToDo consider raising a warning if docker_image and docker_build_dir
        # are both set, in case there's confusion.
        tag = (venv.envconfig.docker_image if venv.envconfig.docker_image
               else f'tid-{socket.gethostname().lower()}-{Path(os.getcwd()).name.lower()}')

        if ':' not in tag:
            tag = f'{tag}:latest'

        build_args = {}

        if venv.envconfig.docker_build_base_arg:
            build_base_image = util.get_default_image(venv.envconfig.envname)
            build_args['BASE'] = build_base_image

        # Build the image
        image, _output = client.images.build(
            buildargs=build_args,
            path=docker_build_dir,
            tag=tag)
        base_image = tag

    else:
        # use a pulled/available image:
        base_image = get_base_image(venv)


    docker_image = main.build_testing_image(base_image, client)
    venv.envconfig.docker_image = docker_image.id


@hookimpl
def tox_runtest(venv: tox.venv.VirtualEnv, redirect: bool):
    """
    Args:
        `venv`: The VirtualEnv object for this specific environment
        `redirect` (bool): I have no clue what this does yet

    # ToDo it may be valuable to play with redirection to get realtime streaming
        output from the container
    """

    tox.reporter.verbosity1(f'{"" if do_run_in_docker(venv=venv) else "Not "}doing run in docker.')

    if util.is_in_docker():
        tox.reporter.info(f"\nAlready in docker\n{'=' * 13}n")
    else:
        tox.reporter.info(f"\nNot in docker (yet?)\n{'=' * 13}\n")

    if not do_run_in_docker(venv=venv):
        return None

    docker_image = venv.envconfig.docker_image
    venv.run_image = docker_image
    tox.reporter.separator("=", "In Docker", tox.reporter.Verbosity.QUIET)
    try:
        container = main.run_tests(venv, docker_image, remove_container=False)
    except docker.errors.ContainerError as exc:
        # "commands failed" is copied from `tox.venv.test()`, more or less
        venv.status = exc.venv_status or "commands failed"


        # ToDo find stderr lines in logs and color them, instead of repeating

        exc.stderr = exc.stderr.decode()
        tox.reporter.separator("-", "Container Logs (stdout + stderr)", tox.reporter.Verbosity.QUIET)
        tox.reporter.line(exc.container.logs().decode())
        tox.reporter.separator("-", "Container Stderr", tox.reporter.Verbosity.QUIET)
        tox.reporter.error('\n' + exc.stderr)
        exc.container.remove()
        return False
    else:
        container.remove()
    return True
