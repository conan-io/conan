from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, Extender, COMMAND_GROUPS
from conans.cli.commands import CommandResult
from conans.cli.commands.list import list_recipes_cli_formatter, json_formatter
from conans.cli.common import get_remote_selection
from conans.errors import NotFoundException, PackageNotFoundException

search_formatters = {
    "cli": list_recipes_cli_formatter,
    "json": json_formatter
}


# FIXME: "conan search" == "conan list recipes -r="*" -c" --> implement @conan_alias_command??
@conan_command(group=COMMAND_GROUPS['consumer'], formatters=search_formatters)
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
        except (NotFoundException, PackageNotFoundException):
            # This exception must be caught manually due to a server inconsistency:
            # Artifactory API returns an empty result if the recipe doesn't exist, but
            # Conan Server returns a 404. This probably should be fixed server side,
            # but in the meantime we must handle it here
            pass
        except Exception as e:
            result.error = str(e)
        results.append(result)
    return results
