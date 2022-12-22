from collections import OrderedDict

from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command
from conan.cli.commands.list import print_list_text, print_list_json
from conan.internal.api.select_pattern import ListPattern
from conans.errors import ConanException


# FIXME: "conan search" == "conan list recipes -r="*" -c" --> implement @conan_alias_command??
@conan_command(group="Consumer", formatters={"text": print_list_text,
                                             "json": print_list_json})
def search(conan_api: ConanAPI, parser, *args):
    """
    Searches for package recipes in a remote or remotes
    """
    parser.add_argument('reference', help="Recipe reference to search for."
                                          "It can contain * as wildcard at any reference field.")
    parser.add_argument("-r", "--remote", action="append",
                        help="Remote names. Accepts wildcards. If not specified it searches "
                             "in all the remotes")
    args = parser.parse_args(*args)

    remotes = conan_api.remotes.list(args.remote)
    if not remotes:
        raise ConanException("There are no remotes to search from")

    results = OrderedDict()
    for remote in remotes:
        ref_pattern = ListPattern(args.reference)
        try:
            list_bundle = conan_api.list.select(ref_pattern, package_query=None, remote=remote)
        except Exception as e:
            results[remote.name] = {"error": str(e)}
        else:
            results[remote.name] = list_bundle.serialize() if args.format == "json" else list_bundle.recipes
    return {
        "results": results,
        "conan_api": conan_api
    }
