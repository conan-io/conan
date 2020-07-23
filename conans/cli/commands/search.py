import json

from conans.client.output import Color
from conans.errors import NoRemoteAvailable
from conans.cli.command import conan_command, Extender


def output_search_cli(info, out):
    results = info["results"]
    for remote_info in results:
        source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
        out.writeln("{}:".format(source), Color.BRIGHT_WHITE)
        for conan_item in remote_info["items"]:
            reference = conan_item["recipe"]["id"]
            out.writeln(" {}".format(reference))


def output_search_json(info, out):
    results = info["results"]
    myjson = json.dumps(results, indent=4)
    out.writeln(myjson)


def apiv2_search_recipes(query, remote_patterns=None, local_cache=False):
    remote = None
    if remote_patterns is not None and len(remote_patterns) > 0:
        remote = remote_patterns[0].replace("*", "remote")

    if remote and "bad" in remote:
        raise NoRemoteAvailable("Remote '%s' not found in remotes" % remote)

    search_results = {"results": [{"remote": remote,
                                   "items": [{"recipe": {"id": "app/1.0"}},
                                             {"recipe": {"id": "liba/1.0"}}]}]}

    return search_results


@conan_command(group="Consumer", formatters={"cli": output_search_cli,
                                                      "json": output_search_json})
def search(*args, conan_api, parser, **kwargs):
    """
    Searches for package recipes whose name contain <query> in a remote or in the local cache
    """

    parser.add_argument('query',
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")

    # TODO: Discuss if --cache and --remote are exclusive
    exclusive_args = parser.add_mutually_exclusive_group()
    exclusive_args.add_argument('-r', '--remote', default=None, action=Extender,
                                help="Remote to search. Accepts wildcards. To search in all remotes use *")
    exclusive_args.add_argument('-c', '--cache', action="store_true",
                                help="Search in the local cache")
    args = parser.parse_args(*args)

    remotes = args.remote or []
    info = apiv2_search_recipes(args.query, remote_patterns=remotes, local_cache=args.cache)
    return info
