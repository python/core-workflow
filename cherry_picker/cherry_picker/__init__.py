"""Backport CPython changes from master to maintenance branches."""
from pathlib import Path
import sys

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

    __version__ = get_version(
        Path(__file__) / '..' / '..' / '..',
        parse=get_parser_with_prefix('cherry-picker')
    )
except ImportError:
    try:
        import pkg_resources
    except ImportError:
        __version__ = '0.0.0dev0'
        del sys.modules['cherry_picker']
    else:
        try:
            __version__ = (
                pkg_resources.get_distribution('cherry-picker').version
            )
        except pkg_resources.DistributionNotFound:
            __version__ = '0.0.0dev0'
            del sys.modules['cherry_picker']
