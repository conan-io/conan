from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, Extender, COMMAND_GROUPS, get_remote_selection
from conans.cli.commands.list import list_recipes_cli_formatter, json_formatter
from conans.errors import NotFoundException, PackageNotFoundException

search_formatters = {
    "cli": list_recipes_cli_formatter,
    "json": json_formatter
}


# FIXME: "conan search" == "conan list recipes --all" --> implement @conan_alias_command??
@conan_command(group=COMMAND_GROUPS['consumer'], formatters=search_formatters)
def search(conan_api: ConanAPIV2, parser, *args, **kwargs):
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
        error = None
        try:
            references = conan_api.search.search_remote_recipes(args.query, remote)
            refs_docs = []
            for reference in references:
                tmp = {
                    "name": reference.name,
                    "id": repr(reference)
                }
                refs_docs.append(tmp)
        except (NotFoundException, PackageNotFoundException):
            # This exception must be caught manually due to a server inconsistency:
            # Artifactory API returns an empty result if the recipe doesn't exist, but
            # Conan Server returns a 404. This probably should be fixed server side,
            # but in the meantime we must handle it here
            refs_docs = []
        except Exception as e:
            error = str(e)
            refs_docs = []

        results.append({
            "remote": remote.name,
            "error": error,
            "results": refs_docs
        })
    return results
