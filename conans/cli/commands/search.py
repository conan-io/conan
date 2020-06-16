import argparse

from conans.errors import ConanException
from conans.client.formatters import FormatterFormats
from conans.cli.command import SmartFormatter, OnceArgument, Extender, conan_command


# conan v2 search:
# conan search "*" will search in the default remote
# to search in the local cache: conan search "*" --cache explicitly

@conan_command(group="Consumer commands")
def search(conan_api, out, *args):
    """
    Searches for package recipes whose name contain <query> in a remote or in the local cache
    """
    search.command_group = "Consumer commands"
    parser = argparse.ArgumentParser(description=search.__doc__, prog="conan search",
                                     formatter_class=SmartFormatter)
    parser.add_argument('query',
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")

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
        info = conan_api.search_recipes(args.query, remote_patterns=remotes,
                                          local_cache=args.cache)
    except ConanException as exc:
        info = exc.info
        raise
    finally:
        out_kwargs = {'out': out, 'f': 'search'}
        FormatterFormats.get(args.output).out(info=info, **out_kwargs)
