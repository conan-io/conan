from conans.cli.command import conan_command, Extender, COMMAND_GROUPS
from conans.cli.commands.list import list_recipes_cli_formatter, json_formatter
from conans.errors import ConanException

search_formatters = {
    "cli": list_recipes_cli_formatter,
    "json": json_formatter
}


@conan_command(group=COMMAND_GROUPS['consumer'], formatters=search_formatters)
def search(conan_api, parser, *args, **kwargs):
    """
    Searches for package recipes in a remote or remotes
    """
    parser.add_argument("query",
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")
    parser.add_argument("-r", "--remote", default=None, action=Extender,
                        help="Remote to search. Accepts wildcards. To search in all remotes use *")
    args = parser.parse_args(*args)

    remotes, error = conan_api.get_active_remotes(args.remote)
    if error:
        raise ConanException(error)

    results = []
    for remote in remotes:
        result, error = conan_api.search_remote_recipes(args.query, remote)
        results.append({
            "remote": remote.name,
            "error": error,
            "results": result
        })
    return results
