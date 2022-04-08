import os

from conan.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand
from conans.cli.commands.list import json_formatter
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


@conan_command(group=COMMAND_GROUPS['consumer'], formatters={"json": json_formatter})
def cache(conan_api: ConanAPIV2, parser, *args):
    """Performs file operations in the local cache (of recipes and packages)"""
    pass


# FIXME: Formatters
@conan_subcommand()
def cache_path(conan_api: ConanAPIV2, parser, subparser, *args):
    """
        Shows the path af a given reference
    """
    subparser.add_argument("reference", help="Recipe reference or Package reference")
    subparser.add_argument("element", choices=['recipe', 'exports', 'exports_sources', 'sources', 'build',
                                               'package'],
                           help="Show the path to the specified element. The 'build' and 'package'"
                                "requires a package reference.")

    args = parser.parse_args(*args)
    pref = _get_package_reference(args.reference)
    if pref:
        path = None
        if args.element == "package":
            path = conan_api.cache.package_path(pref)
        elif args.element == "build":
            path = conan_api.cache.build_path(pref)
        else:
            raise ConanException("'{}' requires a valid recipe reference".format(args.reference))

        out = ConanOutput()
        out.writeln(path)
        return path

    ref = _get_recipe_reference(args.reference)
    if not ref:
        raise ConanException("Invalid recipe or package reference, specify a complete"
                             " reference with revision")

    path = None
    if args.element == "recipe":
        path = os.path.join(conan_api.cache.exports_path(ref), "conanfile.py")
    elif args.element == "exports":
        path = conan_api.cache.exports_path(ref)
    elif args.element == "exports_sources":
        path = conan_api.cache.exports_sources_path(ref)
    elif args.element == "sources":
        path = conan_api.cache.sources_path(ref)
    elif args.element in ("build", "package"):
        raise ConanException("'{}' requires a valid package "
                             "reference".format(args.element))
    out = ConanOutput()
    out.writeln(path)
    return path



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


