
# tox-in-docker

A free-range, grass-fed plugin for dependably running tests using docker
containers when a local version of a given Python is not available.

Features
--------

* TODO


Requirements
------------

### Docker

It is intended to provide podman compatibility in the future, but as of now,
`tox-in-docker` uses [docker](https://docs.docker.com/engine/install) exclusively


Installation
------------

Tox-in-docker is currently not distributed. We intend to distribute it via
[PyPI](https://pypi.org)

Usage
-----

### `tox.ini` configuration

#### Default images
:warning: **No official Jython docker images exist, so there are no defaults
for `jython` environments.**

If no images are provided but `use_docker` is `True`, a default image either
from `python` or `pypy` will be used based off of python name, e.g:

| tox env | Docker image  | Notes |
| ------- | ------------- | ----- |
| `py3`   | `python:3`    |       |
| `py10`  | `python:3.10` | For Python 3.10, `tox` accepts `py10` or `py310` interchangably|
| `py27`  | `python:2.7`  |       |
| `pypy`  | `pypy:latest` |       |

#### `testenv.docker_image`|`testenv.<factor>.docker_image`: (`string`)
A docker image on which to run tests. Any test which has `in_docker` enabled and
does not have this specified will use the [default images](#default-images).

##### Not using `docker_image` from shared `testenv` configuration

If you wish to override general `testenv` settings (from the `[testenv]`
section in `tox.ini`) in order to not define an image for a test (if you wish
to not run that test in a container, _or_ if you wish to define a docker build
dir for a factor), you may use the string 'None' as a value for `docker_image`.

e.g., in this test, py37 will run in python:3.7, spam will run in python:latest,
py38 will run in a bulit container, and frop will not run in a container at all

```inifile
[tox]
minversion = 3.7
isolated_build = true
envlist =
    py37
    py38
    frop
    spam

[testenv]
in_docker = true
docker_image = default

commands =
    echo nope

whitelist_externals =
  echo
  cat

[testenv:py38]
docker_image = None
docker_build_dir = tests/docker
commands =
  echo horp
  cat /baz

[testenv:frop]
in_container = false

```

:warning: **Images used must have:**
  * `bash`
  * `pip`
  * an appropriate Python for the test in question

#### `testenv.docker_artifacts` and `testenv.<environment>.docker_artifacts` (`line list`)
A list of paths, relative to the repo root, of files and folders to copy back
to the source workspace. This is useful for things like coverage reports and
HTML reports, etc.


### Commandline options

  * `--in_container`: :warning: **This option is not meant for direct use.**
    This is the option that `tox-in-docker` uses to revert to default/other
    behavior for the build (once in the container).
  * `--ignore_in_container`: :warning: **This option is not meant for direct use.**
    Using this flag will override the behavior of the `--in_container` option.

Contributing
------------
Contributions are very welcome.
please ensure that test coverage (by percent of statements, not count of
statements) is, at minimum, what it was prior to your work.

### Development Prerequisites

#### Task
https://taskfile.dev/installation/

#### Python `venv`
Python typically ships with the `venv` module, but some built-in/OS-provided
Pythons do not include this.

##### Debian/Ubuntu
OS-packaged Pythons do not include some modules which are properly a part of
the Python stdlib. In order to do development tasks, you must have the
[`venv`](https://docs.python.org/3/library/venv.html#module-venv) module.

Note that you can replace `python3` with a minor version, e.g. `python3.10`.

`sudo apt install python3-venv`

### Testing

Tests may be run via `task` with `task test`
This runs tests with `tox`. If you wish to pass arguments to `tox`, such as
environment specifiers (e.g. `-e py39`), you may pass any arguments you wish
after a double hyphen.

For example, if you wish to only test CPython3.9 and CPython3.10:

`task test -- -e py39 -e py10`


### Tooling

Development and testing tooling is run with [task](#task).

License
-------

Distributed under the terms of the **BSD 2 clause** license, `tox-in-docker` is
free and open source software.


Issues
------

If you encounter any problems, please
[file an issue](https://github.com/zebrafishlabs/tox-in-docker/issues)
along with a detailed description.
