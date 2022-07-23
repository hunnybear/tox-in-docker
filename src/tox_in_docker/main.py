
import docker
import docker.errors
import os
import os.path
import shutil
import tempfile
import tox

from tox_in_docker import util

ENTRYPOINT_MOUNT_DIR = '/entrypoint'
ENTRYPOINT_FILENAME = 'entrypoint'
ENTRYPOINT_PATH = os.path.join(ENTRYPOINT_MOUNT_DIR, ENTRYPOINT_FILENAME)
MOUNT_POINT = '/testing-ro'
TEST_DIR = '/testing'

HERE_MOUNT = {
    os.getcwd(): {
        'bind': MOUNT_POINT
    }
}

# use `.format(env_name=env_name)` to complete this
ENTRYPOINT_SCRIPT_TEMPL = f"""#!/usr/bin/env bash
set -e
set -x

# this makes the tee below pass on the exit code
set -o pipefail

pip install --no-input --disable-pip-version-check tox &>2
cp -r {MOUNT_POINT} {TEST_DIR}
cd {TEST_DIR}

if pip show tox-in-docker &>2 dev/null; then
    ignore_me='--no_tox_in_docker'
fi

echo "ignore me is '${{{{ignore_me}}}}'"
tox $ignore_me -e {{env_name}} | tee /entrypoint/out.log
res=$?
echo "Tox res is ${{{{res}}}}"
exit $res

"""


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

    with tempfile.TemporaryDirectory() as entrypoint_dir:

        volumes = {
            entrypoint_dir: {
                'bind': ENTRYPOINT_MOUNT_DIR
            }
        }

        volumes.update(HERE_MOUNT)
        local_ep_filename = os.path.join(entrypoint_dir, ENTRYPOINT_FILENAME)

        # Create the entrypoint script
        with open(local_ep_filename, 'w') as file_handle:
            file_handle.write(ENTRYPOINT_SCRIPT_TEMPL.format(
                env_name=env_name))
        os.chmod(local_ep_filename, 0o774)
        print(f'\nRunning env {env_name} in {image}!\n')
        lines = []
        try:
            for line in docker_client.containers.run(
                    image=image,
                    volumes=volumes,
                    stream=True,
                    entrypoint=ENTRYPOINT_PATH):
                print(line.decode())
                lines.append(line)
        except docker.errors.ContainerError as run_exc:
            copy_dir = f'/tmp/failed_entrypoint-{env_name}'
            if os.path.exists(copy_dir):
                last_dir = copy_dir + '.last'
                if os.path.exists(last_dir):
                    shutil.rmtree(last_dir)
                shutil.move(copy_dir, last_dir)
            shutil.copytree(entrypoint_dir, copy_dir)
            print(run_exc)
            raise

    return b'/n'.join(lines).decode()
