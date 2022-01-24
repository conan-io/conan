from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, Extender, COMMAND_GROUPS
from conans.cli.commands import CommandResult
from conans.cli.commands.list import print_list_recipes, json_formatter
from conans.cli.common import get_remote_selection


# FIXME: "conan search" == "conan list recipes -r="*" -c" --> implement @conan_alias_command??
@conan_command(group=COMMAND_GROUPS['consumer'], formatters={"json": json_formatter})
def search(conan_api: ConanAPIV2, parser, *args):
    """
    Searches for package recipes in a remote or remotes
    """
    parser.add_argument("query",
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")
    parser.add_argument("-r", "--remote", default="*", action=Extender,
                        help="Remote names. Accepts wildcards. If not specified it searches "
                             "in all remotes")
    args = parser.parse_args(*args)

    results = []
    remotes = get_remote_selection(conan_api, args.remote)
    for remote in remotes:
        result = CommandResult(remote=remote)
        try:
            result.elements = conan_api.search.recipes(args.query, remote)
        except Exception as e:
            result.error = str(e)
        results.append(result)
    print_list_recipes(results)
    return results
