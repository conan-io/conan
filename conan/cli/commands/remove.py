from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern, MultiPackagesList
from conan.cli import make_abs_path
from conan.cli.command import conan_command, OnceArgument
from conans.client.userio import UserInput
from conans.errors import ConanException


@conan_command(group="Consumer")
def remove(conan_api: ConanAPI, parser, *args):
    """
    Remove recipes or packages from local cache or a remote.

    - If no remote is specified (-r), the removal will be done in the local conan cache.
    - If a recipe reference is specified, it will remove the recipe and all the packages, unless -p
      is specified, in that case, only the packages matching the specified query (and not the recipe)
      will be removed.
    - If a package reference is specified, it will remove only the package.
    """
    parser.add_argument('pattern', nargs="?",
                        help="A pattern in the form 'pkg/version#revision:package_id#revision', "
                             "e.g: zlib/1.2.13:* means all binaries for zlib/1.2.13. "
                             "If revision is not specified, it is assumed latest one.")
    parser.add_argument('-c', '--confirm', default=False, action='store_true',
                        help='Remove without requesting a confirmation')
    parser.add_argument('-p', '--package-query', action=OnceArgument,
                        help="Remove all packages (empty) or provide a query: "
                             "os=Windows AND (arch=x86 OR compiler=gcc)")
    parser.add_argument('-r', '--remote', action=OnceArgument,
                        help='Will remove from the specified remote')
    parser.add_argument("-l", "--list", help="Package list file")
    args = parser.parse_args(*args)

    ui = UserInput(conan_api.config.get("core:non_interactive"))
    remote = conan_api.remotes.get(args.remote) if args.remote else None

    def confirmation(message):
        return args.confirm or ui.request_boolean(message)

    if args.list:
        listfile = make_abs_path(args.list)
        multi_package_list = MultiPackagesList.load(listfile)
        package_list = multi_package_list["Local Cache" if not args.remote else args.remote]
    else:
        ref_pattern = ListPattern(args.pattern, rrev="*", prev="*")
        package_list = conan_api.list.select(ref_pattern, args.package_query, remote)

    if ref_pattern.package_id is None:
        if args.package_query is not None:
            raise ConanException('--package-query supplied but the pattern does not match packages')
        for ref, _ in package_list.refs():
            if confirmation("Remove the recipe and all the packages of '{}'?"
                            "".format(ref.repr_notime())):
                conan_api.remove.recipe(ref, remote=remote)
    else:
        for ref, ref_bundle in package_list.refs():
            for pref, _ in package_list.prefs(ref, ref_bundle):
                if confirmation("Remove the package '{}'?".format(pref.repr_notime())):
                    conan_api.remove.package(pref, remote=remote)
