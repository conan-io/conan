import fnmatch

from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.conan_app import ConanApp
from conans.client.userio import UserInput
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['consumer'])
def remove(conan_api: ConanAPIV2, parser, *args):
    """
    Removes recipes or packages from local cache or a remote.
    - If no remote is specified (-r), the removal will be done in the local conan cache.
    - If a recipe reference is specified, it will remove the recipe and all the packages, unless -p
      is specified, in that case, only the packages matching the specified query (and not the recipe)
      will be removed.
    - If a package reference is specified, it will remove only the package.
    """
    _not_specified_ = object()

    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as"
                                          "wildcard at any reference field. e.g: lib/*")
    parser.add_argument('-f', '--force', default=False, action='store_true',
                        help='Remove without requesting a confirmation')
    parser.add_argument('-p', '--package-query', action='store', default=_not_specified_, nargs='?',
                        help="Remove all packages (empty) or provide a query: "
                             "os=Windows AND (arch=x86 OR compiler=gcc)")
    parser.add_argument('-r', '--remote', action=OnceArgument,
                        help='Will remove from the specified remote')
    args = parser.parse_args(*args)

    ui = UserInput(conan_api.config.get("core:non_interactive"))
    remote = conan_api.remotes.get(args.remote) if args.remote else None
    remove_all_packages = args.package_query is None
    query = args.package_query if args.package_query != _not_specified_ else None

    def confirmation(message):
        return args.force or ui.request_boolean(message)

    def raise_if_package_not_found(_prefs):
        if not _prefs and "*" not in args.reference and args.package_query == _not_specified_:
            raise ConanException("Binary package not found: '{}'".format(args.reference))

    if ":" in args.reference and remove_all_packages:
        raise ConanException("The -p argument cannot be used with a package reference")

    if ":" in args.reference or query:
        prefs = conan_api.search.package_revisions(args.reference, remote=remote, query=query)
        raise_if_package_not_found(prefs)
        for pref in prefs:
            if confirmation("Remove the package '{}'?".format(pref.repr_notime())):
                conan_api.remove.package(pref, remote=remote)
    else:
        refs = conan_api.search.recipe_revisions(args.reference, remote=remote)
        if not refs and "*" not in args.reference:
            raise ConanException("Recipe not found: '{}'".format(args.reference))
        if remove_all_packages:
            for ref in refs:
                if confirmation("Remove all packages from '{}'?".format(ref.repr_notime())):
                    conan_api.remove.all_recipe_packages(ref, remote=remote)
        else:
            for ref in refs:
                if confirmation("Remove the recipe and all the packages of '{}'?"
                                "".format(ref.repr_notime())):
                    conan_api.remove.recipe(ref, remote=remote)
