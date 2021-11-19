
# tox-in-docker

A free-range, grass-fed plugin for dependably running tests using docker
containers.

Features
--------

* TODO


Requirements
------------

* TODO


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

| tox env &nbsp; &nbsp;| Docker image &nbsp; &nbsp;|
| ------- | ------------- |
| `py3`   | `python:3`    |
| `py27`  | `python:2.7`  |
| `pypy`  | `pypy:latest` |

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
Contributions are very welcome. Tests can be run with [tox](https://tox.readthedocs.io/en/latest/),
please ensure the coverage at least stays the same before you submit a pull request.

### Running tests with poetry

`poetry run tox` (or, `poetry run tox -e <environment>`)

License
-------

Distributed under the terms of the **BSD 2 caluse** license, `tox-in-docker` is
free and open source software.


Issues
------

If you encounter any problems, please
[file an issue](https://github.com/zebrafishlabs/tox-in-docker/issues)
along with a detailed description.
