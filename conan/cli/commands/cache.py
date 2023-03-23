from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern
from conan.api.output import cli_out_write
from conan.cli.command import conan_command, conan_subcommand, OnceArgument
from conan.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


@conan_command(group="Consumer")
def cache(conan_api: ConanAPI, parser, *args):
    """
    Perform file operations in the local cache (of recipes and/or packages).
    """
    pass


@conan_subcommand(formatters={"text": cli_out_write})
def cache_path(conan_api: ConanAPI, parser, subparser, *args):
    """
    Show the path to the Conan cache for a given reference.
    """
    subparser.add_argument("reference", help="Recipe reference or Package reference")
    subparser.add_argument("--folder", choices=['export_source', 'source', 'build'],
                           help="Path to show. The 'build'"
                                " requires a package reference. If not specified it shows 'exports'"
                                " path ")

    args = parser.parse_args(*args)
    try:
        pref = PkgReference.loads(args.reference)
    except ConanException:
        pref = None

    if not pref:  # Not a package reference
        ref = RecipeReference.loads(args.reference)
        if args.folder is None:
            path = conan_api.cache.export_path(ref)
        elif args.folder == "export_source":
            path = conan_api.cache.export_source_path(ref)
        elif args.folder == "source":
            path = conan_api.cache.source_path(ref)
        else:
            raise ConanException(f"'--folder {args.folder}' requires a valid package reference")
    else:
        if args.folder is None:
            path = conan_api.cache.package_path(pref)
        elif args.folder == "build":
            path = conan_api.cache.build_path(pref)
        else:
            raise ConanException(f"'--folder {args.folder}' requires a recipe reference")
    return path


@conan_subcommand()
def cache_clean(conan_api: ConanAPI, parser, subparser, *args):
    """
    Remove non-critical folders from the cache, like source, build and/or download
    (.tgz store) ones.
    """
    subparser.add_argument("pattern", help="Selection pattern for references to clean")
    subparser.add_argument("-s", "--source", action='store_true', default=False,
                           help="Clean source folders")
    subparser.add_argument("-b", "--build", action='store_true', default=False,
                           help="Clean build folders")
    subparser.add_argument("-d", "--download", action='store_true', default=False,
                           help="Clean download folders")
    subparser.add_argument('-p', '--package-query', action=OnceArgument,
                           help="Remove only the packages matching a specific query, e.g., "
                                "os=Windows AND (arch=x86 OR compiler=gcc)")
    args = parser.parse_args(*args)

    if not args.source and not args.build and not args.download:
        raise ConanException("Define at least one argument among [--source, --build, --download]")

    ref_pattern = ListPattern(args.pattern, rrev="*", package_id="*", prev="*")
    package_list = conan_api.list.select(ref_pattern, package_query=args.package_query)
    conan_api.cache.clean(package_list, source=args.source, build=args.build,
                          download=args.download)


@conan_subcommand(formatters={"text": cli_out_write})
def cache_check_integrity(conan_api: ConanAPI, parser, subparser, *args):
    """
    Check the integrity of the local cache for the given references
    """
    subparser.add_argument("pattern", help="Selection pattern for references to check integrity for")
    subparser.add_argument('-p', '--package-query', action=OnceArgument,
                           help="Only the packages matching a specific query, e.g., "
                                "os=Windows AND (arch=x86 OR compiler=gcc)")
    args = parser.parse_args(*args)

    ref_pattern = ListPattern(args.pattern, rrev="*", package_id="*", prev="*")
    package_list = conan_api.list.select(ref_pattern, package_query=args.package_query)
    conan_api.cache.check_integrity(package_list)
