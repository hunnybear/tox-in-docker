
import docker
import os
import shlex

MOUNT_POINT = '/testing-ro'
TEST_DIR = '/testing'

HERE_MOUNT = {
    os.getcwd(): {
        'bind': MOUNT_POINT
    }
}


def run_tests(images=None):
    if images is None:
        images = ['python:latest']

    client = docker.client.DockerClient()
    cmd = get_test_cmd()

    results = {}

    # ToDo entrypoint?
    for image in images:
        results[image] = client.containers.run(image, cmd, volumes=HERE_MOUNT)

    return results


def get_test_cmd():

    cmds = [
        ['pip', 'install', '--no-input', 'tox'],
        ['cp', '-r', MOUNT_POINT, TEST_DIR],
        ['cd', TEST_DIR],
        ['tox']
    ]

    bash_cmd = ';'.join(shlex.join(cmd) for cmd in cmds)

    full_cmd = shlex.join(['bash', '-c', bash_cmd])

    return full_cmd


