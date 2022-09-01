
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

ENTRYPOINT_PERMS = stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

# use `.format(env_name=env_name)` to complete this
# ToDo diff state of cwd so that local diffs are copied over
ENTRYPOINT_SCRIPT_TEMPL = f"""#!/bin/bash
set -e
set -x

if test -d {MOUNT_POINT}/.git ; then
    cd {MOUNT_POINT}
    # Create a local git remote and push to it. This is _much_ faster than copying
    # the whole directory, and avoids colliding temp files
    # ToDo: handle this for non-git cases, and replace git if the new method is
    # performant
    BRANCH=$(git branch --show-current)
    # Get a diff to patch the working copy
    git diff > /tmp/git.patch
    git init {MOUNTED_WORKING_DIR} 2> /dev/null
    git push {MOUNTED_WORKING_DIR}
    cd {MOUNTED_WORKING_DIR}
    git checkout "${{BRANCH}}" 2> /dev/null
    git apply /tmp/git.patch
elif test -n "$(ls -A {MOUNT_POINT} 2> /dev/null)" ; then
    rsync -avz {MOUNT_POINT} {MOUNTED_WORKING_DIR}
fi

if pip show tox-in-docker 2> /dev/null; then
    ignore_me='--no_tox_in_docker'
fi

LOG_DIR=$(test -d {MOUNTED_WORKING_DIR} && echo "{MOUNTED_WORKING_DIR}" || echo "/var/log")

# Don't immediately fail if tox fails, we want to cleanup (fix perms)
set +e
tox --version

set -o pipefail
tox $ignore_me "$@" | tee "${{LOG_DIR}}/out.log"
res=$?
set +o pipefail

chown -R {os.getuid()}:{os.getgid()} {MOUNTED_WORKING_DIR}

echo "Tox res is ${{res}}"
exit $res

"""

# I'm not sure if keeping these to single statements in the try statements
# is a foolish consistency (could combine them all in one and that _should_
# work.)

try:
    MY_UID = os.getuid()
except OSError:
    MY_UID = pathlib.Path().stat().st_uid

try:
    MY_GID = os.getgid()
except OSError:
    MY_GID = pathlib.Path().stat().st_gid

try:
    MY_USERNAME = os.getlogin()
except OSError:
    MY_USERNAME = pathlib.Path().owner()

DOCKERFILE_TEMPL = f"""FROM {{base}}

ARG UNAME={MY_USERNAME}
ARG UID={MY_UID}
ARG GID={MY_GID}

RUN groupadd -g $GID -o $UNAME
RUN useradd -m -u $UID -g $GID -o -s /bin/bash $UNAME

RUN pip install --no-input --disable-pip-version-check tox
RUN apt update && apt install -y git sudo rsync

# Remove secure path from sudoers so we can get pythons and such
RUN sed '/^Defaults[[:space:]]\\+secure_path/d' /etc/sudoers > /tmp/sudoers
RUN echo "$UNAME ALL=(ALL:ALL) NOPASSWD:ALL" >> /tmp/sudoers
# ensure sudoers is valid
RUN visudo -cf /tmp/sudoers && cp /tmp/sudoers /etc/sudoers

RUN mkdir {MOUNTED_WORKING_DIR} {MOUNT_POINT} /entrypoint
RUN chown $UID:$GID {MOUNTED_WORKING_DIR} {MOUNT_POINT} /entrypoint


WORKDIR {MOUNT_POINT}
COPY {ENTRYPOINT_FILENAME} /entrypoint/{ENTRYPOINT_FILENAME}
VOLUME {MOUNTED_WORKING_DIR}
USER $UNAME
ENTRYPOINT ["/usr/bin/sudo", "/entrypoint/{ENTRYPOINT_FILENAME}"]

"""


@cache
def build_testing_image(base: str, client:docker.client.DockerClient = None):
    """
    Build the testing image for a given version of Python
    """

    if client is None:
        client = docker.client.from_env()

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
        docker_client = docker.client.from_env()

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

        print(f'\nRunning env {env_name} in `{image}`!\n')
        lines = []

        # For debugging. Having trouble? Throw a breakpoint in here and this
        # var should have a CLI command to drop into bash on the image
        run_cmd = ' '.join([
            f'docker run -it --entrypoint /bin/bash -u {os.getuid()} -v ',
            ' -v '.join([f'\'{src}:{mount["bind"]}:{mount["mode"]}\''
                for  src, mount in volumes.items()]),
            f' {image}'])

        # If you don't have your IDE/PDB set up for doing breakpoints for you,
        # This snippet below will break
        # if not util.is_in_docker():
        #    import pdb
        #    pdb.set_trace()

        for line in docker_client.containers.run(
                image=image,
                volumes=volumes,
                stream=True,
                command=['-e', env_name],
                user=os.getuid()):
            print(line.decode())
            lines.append(line)

    return b'/n'.join(lines).decode()
