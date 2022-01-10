from contextlib import contextmanager

from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, Extender, OnceArgument
from conans.cli.commands import CommandResult
from conans.cli.conan_app import ConanApp
from conans.client.userio import UserInput
from conans.errors import ConanException, NotFoundException, PackageNotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class ReferenceArgumentParser:

    def __init__(self, value):
        self.ref = None
        self.pref = None
        try:
            self.pref = PkgReference.loads(value)
            return
        except ConanException:
            pass
        try:
            self.ref = RecipeReference.loads(value)
        except ConanException:
            # Not a complete pattern, recipe name
            pass

    @property
    def recipe_has_patterns(self):
        return "*" in repr(self.ref) if self.ref else "*" in repr(self.pref.ref)

    @property
    def package_has_patterns(self):
        return "*" in repr(self.pref)

    @property
    def is_targeting_recipe(self):
        return not self.is_targeting_package

    @property
    def is_targeting_package(self):
        return self.pref is not None


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
    UNSPECIFIED = object()

    parser.add_argument('reference', help="Recipe reference, package reference or fnmatch pattern "
                                          "for recipe references.")

    parser.add_argument('-f', '--force', default=False, action='store_true',
                        help='Remove without requesting a confirmation')
    parser.add_argument('-p', '--package-query', action='store', default=UNSPECIFIED, nargs='?',
                        help="Remove all packages (empty) or provide a query: "
                             "os=Windows AND (arch=x86 OR compiler=gcc)")
    parser.add_argument('-r', '--remote', action=OnceArgument,
                        help='Will remove from the specified remote')
    args = parser.parse_args(*args)

    parsed_ref = ReferenceArgumentParser(args.reference)
    app = ConanApp(conan_api.cache_folder)
    ui = UserInput(app.cache.new_config["core:non_interactive"])
    remote = conan_api.remotes.get(args.remote) if args.remote else None

    def confirmation(message):
        return args.force or ui.request_boolean(message)

    if parsed_ref.is_targeting_package:
        if parsed_ref.pref.ref.revision is None:
            raise ConanException("To remove a package specify a recipe revision or a pattern")
        if parsed_ref.recipe_has_patterns:
            # Pattern, we have to list all recipe revisions to see what matches
            for r in conan_api.search.recipes(repr(parsed_ref.pref.ref), remote):
                # From the remotes we cannot receive revisions using the search, we have to list all
                complete_refs = conan_api.list.recipe_revisions(r, remote)
                for ref in complete_refs:
                    # FIXME: Optimization of parsed_ref.package_has_patterns
                    pkg_configs = conan_api.list.packages_configurations(ref, remote)
                    if args.package_query != UNSPECIFIED:
                        prefs = conan_api.tools.filter_packages_configurations(pkg_configs,
                                                                               args.package_query)
                    else:
                        prefs = pkg_configs.keys()

                    for pref in prefs:
                        complete_prefs = conan_api.list.package_revisions(pref, remote)
                        for complete_pref in complete_prefs:
                            if PACKAGE REFERENCE MATCHES:
                                conan_api.remove.package(complete_pref, remote)

    else:
        def _remove_recipe(the_ref):
            if args.package_query == UNSPECIFIED:
                conan_api.remove.recipe(the_ref)  # Recipe and all packages
            else:  # Remove packages from recipe
                if not args.package_query:  # All packages
                    if confirmation("Are you sure you want to delete all packages from {}"
                                    "?".format(the_ref.repr_notime())):
                        conan_api.remove.all_recipe_packages(the_ref)
                else:  # Some packages
                    pkg_configs = conan_api.list.packages_configurations(the_ref, remote)
                    prefs = conan_api.tools.filter_packages_configurations(pkg_configs,
                                                                           args.package_query)
                    for pref in prefs:
                        complete_prefs = conan_api.list.package_revisions(pref, remote)
                        for complete_pref in complete_prefs:
                            conan_api.remove.package(complete_pref, remote)

        if not parsed_ref.recipe_has_patterns:  # This is an optimization to not search
            _remove_recipe(parsed_ref.ref)  # Direct recipe reference to remove
            return

        # Pattern, we have to list all recipe revisions to see what matches
        for r in conan_api.search.recipes(args.reference, remote):
            # From the remotes we cannot receive revisions using the search, we have to list all
            complete_refs = conan_api.list.recipe_revisions(r, remote)
            for _r in complete_refs:
                if conan_api.tools.is_recipe_matching(_r, args.reference):
                    _remove_recipe(_r)
