
import docker
import docker.errors
from functools import cache
from io import BytesIO
import os
import os.path
import pathlib
import shutil
import stat
import tempfile
import tox

from tox_in_docker import util

MOUNTED_WORKING_DIR = '/working_dir'
ENTRYPOINT_FILENAME = 'entrypoint'
ENTRYPOINT_PATH = os.path.join(MOUNTED_WORKING_DIR, ENTRYPOINT_FILENAME)
MOUNT_POINT = '/testing-ro'
TEST_DIR = '/testing'

HERE_MOUNT = {
    os.getcwd(): {
        'bind': MOUNT_POINT,
        'mode': 'ro'
    }
}

ENTRYPOINT_PERMS = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR

# use `.format(env_name=env_name)` to complete this
ENTRYPOINT_SCRIPT_TEMPL = f"""#!/usr/bin/env bash
set -e
set -x

if test -d {MOUNT_POINT}/.git; then

    # Create a local git remote and push to it. This is _much_ faster than copying
    # the whole directory, and avoids colliding temp files
    # ToDo: handle this for non-git cases, and replace git if the new method is
    # performant
    BRANCH=$(git branch --show-current)
    git init {MOUNTED_WORKING_DIR}
    git push {MOUNTED_WORKING_DIR}
    cd {MOUNTED_WORKING_DIR}
    git checkout "${{BRANCH}}"
fi

if pip show tox-in-docker &>2 dev/null; then
    ignore_me='--no_tox_in_docker'
fi

echo "ignore me is '${{ignore_me}}'"
tox $ignore_me "$@" | tee {MOUNTED_WORKING_DIR}/out.log
res=$?
echo "Tox res is ${{res}}"
exit $res

"""

DOCKERFILE_TEMPL = f"""FROM {{base}}

RUN pip install --no-input --disable-pip-version-check tox
RUN apt update && apt install -y git
RUN mkdir {MOUNTED_WORKING_DIR} {MOUNT_POINT}
WORKDIR {MOUNT_POINT}
COPY {ENTRYPOINT_FILENAME} {MOUNTED_WORKING_DIR}/{ENTRYPOINT_FILENAME}

ENTRYPOINT ["{MOUNTED_WORKING_DIR}/{ENTRYPOINT_FILENAME}"]

"""

@cache
def build_testing_image(base: str, client:docker.client.DockerClient = None):
    """
    Build the testing image for a given version of Python
    """

    if client is None:
        client = docker.client.DockerClient()

    original_cwd = os.getcwd()
    dockerfile = BytesIO(DOCKERFILE_TEMPL.format(base=base).encode())
    # ToDo revisit ignore cleanup errors
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as build_dir:
        try:
            entrypoint_path = pathlib.Path(build_dir).joinpath(ENTRYPOINT_FILENAME)
            entrypoint_path.write_text(ENTRYPOINT_SCRIPT_TEMPL)
            entrypoint_path.chmod(ENTRYPOINT_PERMS)

            dockerfile_path = pathlib.Path(build_dir).joinpath('Dockerfile')
            dockerfile_path.write_text(DOCKERFILE_TEMPL.format(base=base))
            built, _logs = client.images.build(
                path=build_dir,
            #    custom_context=True,
            #    fileobj=dockerfile,
                tag=f'{base}-tox')
        finally:
            os.chdir(original_cwd)
    return built


def run_tests(venv: tox.venv.VirtualEnv, /,
              image=None,
              docker_client=None):
    """
    run tests for the tox environment `env_name`. this will run tests in the
    image `python:latest` if no image is provided.

    Arguments:
        `venv` (`tox.`): The string name of a docker image
        `image` (`str`, optional): The image in which to run tox. defaults to
            `None`, in which case `python:latest: is used.
        `docker_client` (`docker.client.DockerClient`, optional): A docker
            client to use for managing the test run. If none is provided, one
            will be created.

    ToDo:
        * Make it so that environments which share containers can be batched
            together (especially the python:latest ones)
        * Possibly investigate using one container per image
            - Using dockerfile instead of pulled image may negate this
    """

    if docker_client is None:
        docker_client = docker.client.DockerClient()

    env_name = venv.envconfig.envname

    if image is None:
        image = util.get_default_image(env_name)

    with tempfile.TemporaryDirectory() as working_dir:

        volumes = {
            working_dir: {
                'bind': MOUNTED_WORKING_DIR,
                'mode': 'rw'
            }
        }

        volumes.update(HERE_MOUNT)
        local_ep_filename = os.path.join(working_dir, ENTRYPOINT_FILENAME)

        # Create the entrypoint script
        with open(local_ep_filename, 'w') as file_handle:
            file_handle.write(ENTRYPOINT_SCRIPT_TEMPL)
        os.chmod(local_ep_filename, 0o774)
        print(f'\nRunning env {env_name} in {image}!\n')
        lines = []

        try:
            for line in docker_client.containers.run(
                    image=image,
                    volumes=volumes,
                    stream=True,
                    command=['-e', env_name],
                    user=os.getuid()):
                print(line.decode())
                lines.append(line)

        except docker.errors.ContainerError as run_exc:
            copy_dir = f'/tmp/failed_entrypoint-{env_name}'
            if os.path.exists(copy_dir):
                last_dir = copy_dir + '.last'
                if os.path.exists(last_dir):
                    shutil.rmtree(last_dir)
                shutil.move(copy_dir, last_dir)
            shutil.copytree(working_dir, copy_dir)
            print(run_exc)
            raise

    return b'/n'.join(lines).decode()
