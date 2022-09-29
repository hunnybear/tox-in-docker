import subprocess

def ping() -> bytes:
	return subprocess.check_output(['ping', '-c', '3', '127.0.0.1'])
