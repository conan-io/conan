import json

from conan.api.conan_api import ConanAPIV2
from conan.api.output import ConanOutput
from conan.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand
from conan.cli.commands.list import json_formatter
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


@conan_command(group=COMMAND_GROUPS['consumer'], formatters={"json": json_formatter})
def cache(conan_api: ConanAPIV2, parser, *args):
    """Performs file operations in the local cache (of recipes and packages)"""
    pass


def json_cache_path(res):
    return json.dumps(res, indent=4)


@conan_subcommand(formatters={"json": json_cache_path})
def cache_path(conan_api: ConanAPIV2, parser, subparser, *args):
    """
        Shows the path af a given reference
    """
    subparser.add_argument("reference", help="Recipe reference or Package reference")
    subparser.add_argument("--folder", choices=['exports', 'exports_sources', 'sources', 'build',
                                                'package'], default="exports",
                           help="Show the path to the specified element. The 'build' and 'package'"
                                " requires a package reference. If not specified it shows 'exports'"
                                " path ")

    args = parser.parse_args(*args)
    pref = _get_package_reference(args.reference)
    methods = {"package": conan_api.cache.package_path,
               "build": conan_api.cache.build_path,
               "exports": conan_api.cache.exports_path,
               "exports_sources": conan_api.cache.exports_sources_path,
               "sources": conan_api.cache.sources_path}

    if not pref:  # Not a package reference
        ref = _get_recipe_reference(args.reference)
        if not ref:
            raise ConanException("Invalid recipe or package reference, specify a complete"
                                 " reference with revision")
        if args.folder in ("build", "package"):
            raise ConanException("'--folder {}' requires a valid package reference".format(args.folder))

        method = methods.get(args.folder)
        path = method(ref)
    else:
        method = methods.get(args.folder)
        if args.folder in ("exports", "exports_sources", "sources"):
            path = method(pref.ref)
        else:
            path = method(pref)

    out = ConanOutput()
    out.writeln(path)
    return {"ref": args.reference, "folder": args.folder, "path": path}


def _get_recipe_reference(reference):
    try:
        ref = RecipeReference.loads(reference)
        if not ref.revision:
            return None
        return ref
    except ConanException:
        return None


def _get_package_reference(pref):
    try:
        pref = PkgReference.loads(pref)
        if not pref.revision or not pref.ref.revision:
            return None
        return pref
    except ConanException:
        return None


