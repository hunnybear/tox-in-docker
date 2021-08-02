
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

You can install "tox-in-docker" via [pip](https://pypi.org/project/pip/) from [PyPI](https://pypi.org):

```
pip install tox-in-docker
```

Usage
-----

### `tox.ini` configuration

#### Default images
:warning: **No official Jython docker images exist, so there are no defaults
for `jython` environments.**

If no images are provided, a default image either from `python` or `pypy`, e.g:

| tox env &nbsp; &nbsp;| Docker image &nbsp; &nbsp;|
| ------- | ------------- |
| `py3`   | `python:3`    |
| `py27`  | `python:2.7`  |
| `pypy`  | `pypy:latest` |

#### `testenv.docker_images`: (`line list>`)
A list of docker images on which to run tests. These images will be used as a
dimension on the test matrix. Specifying  `[testenv:<env>].docker_images` will
override this configuration completely


##### Example
if you provide `image-1:latest` and `image-2:1.2.3` to `docker_images`, and
environments `py37` and `py38`, you would end up with this test matrix:

|                  | env: `py37` | env: `py38` |
| ---------------- | ----------- | ----------- |
| `image-1:latest` |  pass/fail  |  pass/fail  |
| `image-2:1.2.3`  |  pass/fail  |  pass/fail  |

  #### `testenv.<env>.docker_images` (`line list`)
Specifying this overrides the global `testenv.docker_images` list for this
environment, **unless** the option `add_docker_images_to_global` is set for
this environment, too.

 #### `testenv:<env>.add_docker_images_to_global` (`bool`)
If this is true, the images specified in `testenv.<env>.docker_images` will be
_added_ to the global images in `testenv.docker_images`


### Commandline options

  * `--in_container`: :warning: **This option is not meant for direct use.**
    This is the option that `tox-in-docker` uses to revert to default/other
    behavior for the build (once in the container).
  * `--ignore_in_container`: :warning: **This option is not meant for direct use.**
    Using this flag will override the behavior of the `--in_container` option.

Contributing
------------
Contributions are very welcome. Tests can be run with [tox](https://tox.readthedocs.io/en/latest/), please ensure
the coverage at least stays the same before you submit a pull request.

License
-------

Distributed under the terms of the **BSD 2 caluse** license, `tox-in-docker` is
free and open source software.


Issues
------

If you encounter any problems, please
[file an issue](https://github.com/zebrafishlabs/tox-in-docker/issues)
along with a detailed description.
