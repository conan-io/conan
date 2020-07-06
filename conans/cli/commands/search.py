import json

from conans.client.output import Color
from conans.errors import ConanException
from conans.cli.cli import OnceArgument, Extender
from conans.cli.command import conan_command


def output_search_cli(info, out):
    results = info["results"]
    for remote_info in results:
        source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
        out.writeln("{}:".format(source), Color.BRIGHT_WHITE)
        for conan_item in remote_info["items"]:
            reference = conan_item["recipe"]["id"]
            out.writeln(" {}".format(reference))


def output_search_json(info, out):
    myjson = json.dumps(info["results"], indent=4)
    out.writeln(myjson)


@conan_command(group="Consumer commands", cli=output_search_cli, json=output_search_json)
def search(*args, conan_api, parser, **kwargs):
    """
    Searches for package recipes whose name contain <query> in a remote or in the local cache
    """

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
        def apiv2_search_recipes(query, remote_patterns=None, local_cache=False):
            remote = None
            if remote_patterns is not None and len(remote_patterns) > 0:
                remote = remote_patterns[0].replace("*", "remote")

            search_results = {"results": [{"remote": remote,
                                           "items": [{"recipe": {"id": "app/1.0"}},
                                                     {"recipe": {"id": "liba/1.0"}}]}]}
            return search_results

        remotes = args.remote or []
        info = apiv2_search_recipes(args.query, remote_patterns=remotes, local_cache=args.cache)
    except ConanException as exc:
        info = exc.info
        raise
    finally:
        return info, args.output
