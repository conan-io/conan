import argparse

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.client.formatters import FormatterFormats
from conans.cli.command import SmartFormatter, OnceArgument, Extender, conan_command


#  This command accepts a conan package reference as input. Could be in different forms:
#  name/version
#  name/version@user/channel
#  name/version@user/channel#<recipe_revision>
#  name/version@user/channel#<recipe_revision>:<package_id>
#  name/version@user/channel#<recipe_revision>:<package_id>#<package_revision>

@conan_command(group="Consumer commands")
def dig(conan_api, out, *args):
    """
    Gets information about available package binaries in the local cache or a remote
    """
    parser = argparse.ArgumentParser(description=dig.__doc__, prog="conan search",
                                     formatter_class=SmartFormatter)
    parser.add_argument('reference',
                        help="Package recipe reference, e.g., 'zlib/1.2.8', \
                             'boost/1.73.0@mycompany/stable'")

    exclusive_args = parser.add_mutually_exclusive_group()
    exclusive_args.add_argument('-r', '--remote', default=None, action=Extender, nargs='?',
                                help="Remote to search. Accepts wildcards. To search in all remotes use *")
    exclusive_args.add_argument('-c', '--cache', action="store_true",
                                help="Search in the local cache")
    parser.add_argument('-o', '--output', default="cli", action=OnceArgument,
                        help="Select the output format: json, html,...")
    args = parser.parse_args(*args)

    try:
        remotes = args.remote if args.remote is not None else []
        ref = ConanFileReference.loads(args.reference)
        info = conan_api.search_packages(ref, query=None,
                                           remote_patterns=remotes,
                                           outdated=False,
                                           local_cache=args.cache)
    except ConanException as exc:
        info = exc.info
        raise
    finally:
        out_kwargs = {'out': out, 'f': 'dig'}
        FormatterFormats.get(args.output).out(info=info, **out_kwargs)
