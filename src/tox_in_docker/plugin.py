import argparse
import functools
import pluggy
import tox
import tox.exception
from tox_in_docker import main


hookimpl = pluggy.HookimplMarker("tox")


class OptionStoreBoolOverride(argparse.Action):
    """
    I'd base this off of argparse.Action._StoreConstAction were it not in the
    private interface.
    """
    overridden = set()

    def __init__(self, const, *args, overrider=False, nargs=0, default=False, type=bool, **kwargs):
        self.overrider = overrider
        super().__init__(*args, const=const, default=default, nargs=nargs, type=type, **kwargs)

    def __call__(self, parser, namespace, values, option_strings=None):

        if not self.overrider and self.dest in self.overridden:
            return False

        setattr(namespace, self.dest, self.const)

        if self.overrider:
            self.overridden.add(self.dest)


action_store_true_overridable = functools.partial(OptionStoreBoolOverride,
                                                  True,
                                                  overrider=False,
                                                  default=False)

action_store_true_overrider = functools.partial(OptionStoreBoolOverride,
                                                False,
                                                overrider=True,
                                                default=False)

@hookimpl
def tox_addoption(parser: tox.config.Parser):
    """Add a command line option for later use"""
    parser.add_argument("--in_container", action=action_store_true_overridable,
                        help="Run")
    parser.add_argument(
        '--ignore_in_container', dest="in_container", action=action_store_true_overrider)
    parser.add_testenv_attribute(
        name="docker_images",
        type="line-list",
        help=" ".join([
            "List of Docker images to run in/add to the testing matrix.",
            "All images _MUST_ have `pip` installed"
        ])
    )


@hookimpl
def tox_configure(config: tox.config.Config):
    """Access your option during configuration"""
    # verbosity0("flag magic is: {}".format(config.option.magic))

    # TODO
    pass


@hookimpl
def tox_runtest(venv: tox.venv.VirtualEnv, redirect: bool):
    """
    Args:
        `venv`:
        `redirect` (bool): I have no clue what this does yet
    """

    envconfig:tox.config.TestenvConfig = venv.envconfig
    return True
