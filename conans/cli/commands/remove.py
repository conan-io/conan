from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, Extender, OnceArgument
from conans.cli.commands import CommandResult
from conans.cli.conan_app import ConanApp
from conans.client.userio import UserInput
from conans.errors import ConanException, NotFoundException, PackageNotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class ReferenceOrPatternArgument:

    def __init__(self, value):
        self.ref = None
        self.pref = None
        self.pattern = None
        try:
            self.pref = PkgReference.loads(value)
            return
        except ConanException:
            pass
        try:
            self.ref = RecipeReference.loads(value)
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
    parser.add_argument('reference', help="Recipe reference, package reference or fnmatch pattern "
                                          "for recipe references.")

    parser.add_argument('-f', '--force', default=False, action='store_true',
                        help='Remove without requesting a confirmation')
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Remove all packages (empty) or provide a query: "
                             "os=Windows AND (arch=x86 OR compiler=gcc)")
    parser.add_argument('-r', '--remote', action=OnceArgument,
                        help='Will remove from the specified remote')
    args = parser.parse_args(*args)

    tmp = ReferenceOrPatternArgument(args.reference)
    app = ConanApp(conan_api.cache_folder)
    ui = UserInput(app.cache.new_config["core:non_interactive"])
    remote = conan_api.remotes.get(args.remote) if args.remote else None

    if tmp.is_package_ref():
        if args.package_query:
            raise ConanException("'-p' cannot be used with a package reference")
        answer = ui.request_boolean("Are you sure you want to delete the package {}?"
                                    "".format(repr(tmp.pref)))
        prefs = [tmp.pref]
        if not tmp.pref.ref.revision:
            prefs = [PkgReference(ref, tmp.pref.package_id, tmp.pref.revision)
                        for ref in conan_api.list.recipe_revisions(tmp.pref.ref, remote)]
        complete_prefs = []
        for pref in prefs:
            complete_prefs.extend([_p for _p in conan_api.list.package_revisions(pref, remote)])

        if answer:
            conan_api.remove.package(tmp.pref, remote)
    else:
        if tmp.is_pattern():
            refs = conan_api.search.recipes(tmp.pattern, remote)
            if not refs:
                raise ConanException("No recipes matching {}".format(tmp.pattern))
        else:
            refs = tmp.ref

        # FIXME: We have to complete the revision from "refs", with latest? or remove from all?
        complete_refs = []
        for ref in refs:
            complete_refs.extend(conan_api.list.recipe_revisions(ref, remote))

        for ref in complete_refs:
            if not args.package_query:
                answer = ui.request_boolean("Are you sure you want to delete the recipe {} "
                                            "and all its packages?".format(repr(ref)))
            else:
                answer = ui.request_boolean("Are you sure you want to delete the recipe {} "
                                            "and the packages matching "
                                            "'{}'?".format(repr(ref), args.package_query))

            if answer:
                if not args.package_query:
                    conan_api.remove.recipe(ref, remote)
                else:
                    configs = conan_api.list.packages_configurations(ref, remote)
                    prefs = conan_api.search.filter_packages_configurations(configs,
                                                                            args.package_query).keys()
                    # FIXME: Remove prefs and only the recipe
