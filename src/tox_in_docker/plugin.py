import pluggy
from tox.reporter import verbosity0

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
def tox_addoption(parser):
    """Add a command line option for later use"""
    parser.add_argument("--magic", action="store", help="this is a magical option")
    parser.add_testenv_attribute(
        name="cinderella",
        type="string",
        default="not here",
        help="an argument pulled from the tox.ini",
    )


@hookimpl
def tox_configure(config):
    """Access your option during configuration"""
    verbosity0("flag magic is: {}".format(config.option.magic))


@hookimpl
def tox_runtest_post(venv):
    verbosity0("cinderella is {}".format(venv.envconfig.cinderella))
