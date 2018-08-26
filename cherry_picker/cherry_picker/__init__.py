"""Backport CPython changes from master to maintenance branches."""
from pathlib import Path
import sys

def get_dist_version():
    try:
        from setuptools_scm import get_version
        from setuptools_scm.git import parse


        def parse_starting_with(prefix, *args, **kwargs):
            """Extract tag with a given prefix."""
            descr_cmd = (
                'git describe --dirty --tags --long '
                '--match {tag_prefix}-*'.format(tag_prefix=prefix)
            )
            return parse(*args, describe_command=descr_cmd, **kwargs)

        def get_parser_with_prefix(prefix):
            """Return a function with git describe command substituted."""
            # Couldn't do this via functools.partial, because of internal
            # check for an argument being a function.
            return lambda *a, **k: parse_starting_with(prefix, *a, **k) 

        return get_version(
            Path(__file__) / '..' / '..' / '..',
            parse=get_parser_with_prefix('cherry-picker')
        )
    except ImportError:
        try:
            import pkg_resources
        except ImportError:
            return '0.0.0dev0'
        else:
            try:
                __version__ = (
                    pkg_resources.get_distribution('cherry-picker').version
                )
            except pkg_resources.DistributionNotFound:
                return '0.0.0dev0'


counter = 0
def __getattr__(name):
    global counter
    if name == '__version__':
        counter += 1
        if counter > 1:
            globals()['__version__'] = get_dist_version()
            del globals()['__getattr__']
            del globals()['counter']
        return version
    raise AttributeError('module {} has no attribute {}'.format(__name__, name))


if sys.version_info < (3, 7):
    class ModuleWrapper:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def __getattr__(self, name):
            global __getattr__
            return __getattr__(name)

    _globals = sys.modules[__name__] = ModuleWrapper(sys.modules[__name__])
