from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command, OnceArgument
from conan.internal.api.select_pattern import SelectPattern
from conans.client.userio import UserInput


@conan_command(group="Consumer")
def remove(conan_api: ConanAPI, parser, *args):
    """
    Removes recipes or packages from local cache or a remote.
    - If no remote is specified (-r), the removal will be done in the local conan cache.
    - If a recipe reference is specified, it will remove the recipe and all the packages, unless -p
      is specified, in that case, only the packages matching the specified query (and not the recipe)
      will be removed.
    - If a package reference is specified, it will remove only the package.
    """
    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as"
                                          "wildcard at any reference field. e.g: lib/*")
    parser.add_argument('-c', '--confirm', default=False, action='store_true',
                        help='Remove without requesting a confirmation')
    parser.add_argument('-p', '--package-query', action=OnceArgument,
                        help="Remove all packages (empty) or provide a query: "
                             "os=Windows AND (arch=x86 OR compiler=gcc)")
    parser.add_argument('-r', '--remote', action=OnceArgument,
                        help='Will remove from the specified remote')
    args = parser.parse_args(*args)

    ui = UserInput(conan_api.config.get("core:non_interactive"))
    remote = conan_api.remotes.get(args.remote) if args.remote else None

    def confirmation(message):
        return args.confirm or ui.request_boolean(message)

    only_recipe = ":" not in args.reference and not args.package_query
    ref_pattern = SelectPattern(args.reference, rrev="*", prev="*")
    select_bundle = conan_api.search.select(ref_pattern, only_recipe, args.package_query, remote)

    if only_recipe:
        for ref in select_bundle.refs():
            if confirmation("Remove the recipe and all the packages of '{}'?"
                            "".format(ref.repr_notime())):
                conan_api.remove.recipe(ref, remote=remote)
    else:
        for pref, _ in select_bundle.prefs():
            if confirmation("Remove the package '{}'?".format(pref.repr_notime())):
                conan_api.remove.package(pref, remote=remote)
