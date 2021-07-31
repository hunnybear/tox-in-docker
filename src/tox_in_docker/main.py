
import docker
import os

MOUNT_POINT = '/testing-ro'
TEST_DIR = '/testing'

HERE_MOUNT = {
    os.getcwd(): {
        'bind': MOUNT_POINT
    }
}

def do_tests():
    cmd = f'bash -c "cp -r {MOUNT_POINT} {TEST_DIR};cd {TEST_DIR}; tox"'

    do_launch(cmd)

# TOREMOVE: these kwargs are definitely not for realz
def do_launch(cmd, image='ubuntu'):

    client = docker.client.DockerClient()

    return(client.containers.run(image, cmd, volumes=HERE_MOUNT))

