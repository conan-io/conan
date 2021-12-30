from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, Extender, OnceArgument
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class ReferenceOrPatternArgument:

    def __init__(self, value):
        self.ref = None
        self.pref = None
        self.pattern = None
        try:
            self.ref = RecipeReference.loads(value)
            return
        except ConanException:
            pass
        try:
            self.pref = PkgReference.loads(value)
        except ConanException:
            self.pattern = value

    def is_recipe_ref(self):
        return self.ref is not None

    def is_package_ref(self):
        return self.pref is not None

    def is_pattern(self):
        return self.pattern is not None


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
    parser.add_argument('reference', nargs="?", help="Recipe reference, package reference or "
                                                     "fnmatch pattern for recipe references.")

    parser.add_argument('-f', '--force', default=False, action='store_true',
                        help='Remove without requesting a confirmation')
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Remove all packages (empty) or provide a query: "
                             "os=Windows AND (arch=x86 OR compiler=gcc)")
    parser.add_argument('-r', '--remote', action=OnceArgument,
                        help='Will remove from the specified remote')
    args = parser.parse_args(*args)

    if args.packages is not None and args.query:
        raise ConanException("'-q' and '-p' parameters can't be used at the same time")

    if args.builds is not None and args.query:
        raise ConanException("'-q' and '-b' parameters can't be used at the same time")

    if args.system_reqs:
        if args.packages:
            raise ConanException("'-t' and '-p' parameters can't be used at the same time")
        if not args.pattern_or_reference:
            raise ConanException("Please specify a valid pattern or reference to be cleaned")

        if check_valid_ref(args.pattern_or_reference):
            return self._conan_api.remove_system_reqs(args.pattern_or_reference)

        return self._conan_api.remove_system_reqs_by_pattern(args.pattern_or_reference)
    else:
        if not args.pattern_or_reference:
            raise ConanException('Please specify a pattern to be removed ("*" for all)')

    try:
        pref = PkgReference.loads(args.pattern_or_reference)
        packages = [pref.package_id]
        pattern_or_reference = repr(pref.ref)
    except ConanException:
        pref = None
        pattern_or_reference = args.pattern_or_reference
        packages = args.packages

    if pref and args.packages:
        raise ConanException("Use package ID only as -p argument or reference, not both")

    return self._conan_api.remove(pattern=pattern_or_reference, query=args.query,
                                  packages=packages, builds=args.builds, src=args.src,
                                  force=args.force, remote_name=args.remote)
