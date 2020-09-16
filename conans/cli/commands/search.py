import json

from conans.client.output import Color
from conans.cli.command import conan_command, Extender


def output_search_cli(info, out):
    for remote_info in info:
        source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
        out.write("{}:".format(source), Color.BRIGHT_WHITE)
        for conan_item in remote_info["items"]:
            reference = conan_item["recipe"]["id"]
            out.write(" {}".format(reference))


def output_search_json(info, out):
    myjson = json.dumps(info, indent=4)
    out.write(myjson)


@conan_command(group="Consumer", formatters={"cli": output_search_cli,
                                                      "json": output_search_json})
def search(conan_api, parser, *args, **kwargs):
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
    info = conan_api.search_recipes(args.query, remote_patterns=remotes, local_cache=args.cache)
    return info
