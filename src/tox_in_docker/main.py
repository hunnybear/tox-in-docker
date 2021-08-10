
import docker
import docker.errors
import os
import shlex
import time

MOUNT_POINT = '/testing-ro'
TEST_DIR = '/testing'

HERE_MOUNT = {
    os.getcwd(): {
        'bind': MOUNT_POINT
    }
}

# use `.format(env_name=env_name)` to complete this
ENTRYPOINT_SCRIPT_TEMPL = """#!/usr/bin/env bash

pip install --no-input --disable-pip-version-check tox


"""


def _docker_test_run(fn):
    """
    Decorator for setting up docker client for run, and cleaning up test
    detritus. This is effectively a context manager wrapper

    We may, in the future, want to be able to save off copies of the config,
    at least in the case of exceptions/errors, or in debug mode.
    """

    def decorated(env_name, image=None):
        docker_client = docker.client.DockerClient()
        leave_swarm = False

        if docker_client.swarm.id is None:
            docker_client.swarm.init()
            leave_swarm = True

        restart_policy = docker.types.RestartPolicy(max_attempts=1)

        entrypoint_config = docker_client.configs.create(
            name=f'{env_name}-entrypoint',
            labels={'tox_env': env_name, 'entrypoint': ""},
            data=ENTRYPOINT_SCRIPT_TEMPL.format(env_name=env_name)
        )

        ep_config_ref = docker.types.ConfigReference(
            entrypoint_config.id,
            config_name=docker_client.configs.get(entrypoint_config.id).name,
            mode=0o774,
            filename='/entrypoint'
        )

        try:
            res = fn(
                env_name,
                docker_client=docker_client,
                image=image,
                configs=[ep_config_ref],
                restart_policy=restart_policy)
        finally:
            # Cleanup my mess
            # remove the config
            entrypoint_config.remove()
            service.remove()
            if leave_swarm:
                # Force because this node is the manger if we inited the swarm
                docker_client.swarm.leave(force=True)

        return res
    return decorated


@_docker_test_run
def run_tests(env_name,
              docker_client,
              image=None,
              configs=None,
              restart_policy=None,
              timeout_sec=300,
              command='/entrypoint'):
    """
    run tests for the tox environment `env_name`. this will run tests in the
    image `python:latest` if no image is provided.

    Arguments:
        `env_name` (`str`): The string name of a docker image
        `image` (`str`, optional): The image in which to run tox. defaults to
            `None`, in which case `python:latest: is used.
        `docker_client` (`docker.client.DockerClient`, optional): A docker
            client to use for managing the test run. If none is provided, one
            will be created.
        `entrypoint_config

    ToDo:
        * Make it so that environments which share containers can be batched
            together (especially the python:latest ones)
        * Possibly investigate using one container per image
            - Using dockerfile instead of pulled image may negate this
    """

    if configs is None:
        configs = []
    if not timeout_sec or timeout_sec < 0:
        timeout_sec = float('inf')

    if restart_policy is None:
        # default RP
        restart_policy = docker.types.RestartPolicy()

    if image is None:
        image = 'python:latest'

    print(f'\nRunning env {env_name} in {image}!\n')

    service = docker_client.services.create(
        image=image,
        command=command,
        maxreplicas=1,
        configs=configs,
        restart_policy=restart_policy
    )

    assert len(service.tasks()) == 1

    running_states = ['NEW', 'PENDING', 'ASSIGNED', 'ACCEPTED', 'PREPARING', 'STARTING', 'RUNNING']

    elapsed = 0
    poll_secs = 5
    while elapsed < timeout_sec:

        if service.tasks()[0]['Status']['state'] in running_states:
            break

        time.sleep(poll_secs)
        elapsed += poll_secs

    results = '\n'.join(service.logs(stdout=True))
    stderr_out = '\n'.join(service.logs(stderr=True))

    print(results)
    print(f'\nSTDERR:\n=======\n{stderr_out}')
    return results


def get_entrypoint(env_name):

    cmds = [
        (True, ['pip', 'install', '--no-input', '--disable-pip-version-check', 'tox']),
        (True, ['cp', '-r', MOUNT_POINT, TEST_DIR]),
        (True, ['cd', TEST_DIR]),
        (False, f'tox $(pip show tox-in-docker &>2 /dev/null && echo -n --no_tox_in_docker) -e "{env_name}"')
    ]

    bash_cmd = ';'.join(shlex.join(cmd) if do_shlex else cmd for do_shlex, cmd in cmds)

    full_cmd = shlex.join(['/usr/bin/env', 'bash', '-c', bash_cmd])

    return full_cmd


