from collections import OrderedDict

from conan.api.conan_api import ConanAPIV2
from conan.cli.command import conan_command, Extender
from conan.cli.commands.list import print_list_recipes, default_json_formatter


# FIXME: "conan search" == "conan list recipes -r="*" -c" --> implement @conan_alias_command??
@conan_command(group="Consumer", formatters={"text": print_list_recipes, "json": default_json_formatter})
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

    remotes = conan_api.remotes.list(args.remote)

    results = OrderedDict()
    for remote in remotes:
        name = getattr(remote, "name", None)
        try:
            results[name] = {"recipes": conan_api.search.recipes(args.query, remote)}
        except Exception as e:
            results[name] = {"error": str(e)}
    return results
