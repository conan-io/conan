import copy
from typing import List

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.commands import json_formatter, CommandResult
from conans.cli.common import get_remote_selection
from conans.cli.output import Color, ConanOutput
from conans.errors import ConanException, InvalidNameException, PackageNotFoundException, \
    NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def _print_common_headers(result: CommandResult):
    out = ConanOutput()
    if result.remote:
        out.writeln(f"{result.remote.name}:", fg=remote_color)
    else:
        out.writeln("Local Cache:", remote_color)


def print_list_recipes(results: List[CommandResult]):
    out = ConanOutput()
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"  ERROR: {result.error}"
            out.writeln(error, fg=error_color)
        elif not result.elements:
            out.writeln("  There are no matching recipe references")
        else:
            current_recipe = None
            for ref in result.elements:
                if ref.name != current_recipe:
                    current_recipe = ref.name
                    out.writeln(f"  {current_recipe}", fg=recipe_color)

                out.writeln(f"    {ref}", fg=reference_color)


def print_list_recipe_revisions(results):
    out = ConanOutput()
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"  ERROR: {result.error}"
            out.writeln(error, fg=error_color)
        elif not result.elements:
            out.writeln(f"  There are no matching recipe references")
        else:
            for ref in result.elements:
                out.writeln(f"  {ref.repr_humantime()}", fg=recipe_color)


def print_list_package_revisions(results):
    out = ConanOutput()
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"  ERROR: {result.error}"
            out.writeln(error, fg=error_color)
        elif not result.elements:
            out.writeln(f"  There are no matching package references")
        else:
            for pref in result.elements:
                out.writeln(f"  {pref.repr_humantime()}", fg=recipe_color)


def print_list_package_ids(results: List[CommandResult]):
    out = ConanOutput()
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"  ERROR: {result.error}"
            out.writeln(error, fg=error_color)
        elif not result.elements:
            out.writeln("  There are no packages")
        else:
            for pref, search_info in result.elements.items():
                _tmp_pref = copy.copy(pref)
                _tmp_pref.revision = None  # Do not show the revision of the package
                out.writeln(f"  {_tmp_pref.repr_notime()}", fg=reference_color)
                if search_info.requires:
                    out.writeln("    requires:", fg=field_color)
                    for req in search_info.requires:
                        out.writeln(f"      {req}", fg=value_color)
                if search_info.settings:
                    out.writeln(f"    settings:", fg=field_color)
                    for name, val in search_info.settings.items():
                        out.writeln(f"      {name}={val}", fg=value_color)
                if search_info.options:
                    out.writeln(f"    options:", fg=field_color)
                    for name, val in search_info.options.items():
                        out.writeln(f"      {name}={val}", fg=value_color)


def _add_remotes_and_cache_options(subparser):
    remotes_group = subparser.add_mutually_exclusive_group()
    remotes_group.add_argument("-r", "--remote", default=None, action=Extender,
                               help="Remote names. Accepts wildcards")
    subparser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")


@conan_subcommand(formatters={"json": json_formatter})
def list_recipes(conan_api, parser, subparser, *args):
    """
    Search available recipes in the local cache or in the remotes
    """
    subparser.add_argument(
        "query",
        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'"
    )
    _add_remotes_and_cache_options(subparser)
    args = parser.parse_args(*args)

    use_remotes = args.remote
    results = []

    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        result = CommandResult()
        try:
            references = conan_api.search.recipes(args.query)
        except Exception as e:
            result.error = str(e)
        else:
            result.elements = references
        results.append(result)

    if use_remotes:
        remotes = get_remote_selection(conan_api, args.remote)
        for remote in remotes:
            result = CommandResult(remote=remote)
            try:
                result.elements = conan_api.search.recipes(args.query, remote)
            except Exception as e:
                result.error = str(e)
            results.append(result)

    print_list_recipes(results)
    return results


@conan_subcommand(formatters={"json": json_formatter})
def list_recipe_revisions(conan_api, parser, subparser, *args):
    """
    List all the revisions of a recipe reference.
    """
    subparser.add_argument("reference", help="Recipe reference, e.g., libyaml/0.2.5")
    _add_remotes_and_cache_options(subparser)
    args = parser.parse_args(*args)

    ref = RecipeReference.loads(args.reference)
    if ref.revision:
        raise ConanException(f"Cannot list the revisions of a specific recipe revision")

    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not args.remote:
        result = CommandResult()
        result["ref"] = ref
        try:
            result.elements = conan_api.list.recipe_revisions(ref)
        except Exception as e:
            result.error = str(e)

        results.append(result)
    if args.remote:
        remotes = get_remote_selection(conan_api, args.remote)
        for remote in remotes:
            result = CommandResult(remote=remote)
            result["ref"] = ref
            try:
                result.elements = conan_api.list.recipe_revisions(ref, remote=remote)
            except NotFoundException:
                result.elements = []
            except Exception as e:
                result.error = str(e)
            results.append(result)

    print_list_recipe_revisions(results)
    return results


@conan_subcommand(formatters={"json": json_formatter})
def list_package_revisions(conan_api, parser, subparser, *args):
    """
    List all the revisions of a package ID reference.
    """
    subparser.add_argument("package_reference", help="Package reference, e.g., libyaml/0.2.5"
                                                     "#80b7cbe095ac7f38844b6511e69e453a:"
                                                     "ef93ea55bee154729e264db35ca6a16ecab77eb7")
    _add_remotes_and_cache_options(subparser)
    args = parser.parse_args(*args)

    try:
        pref = PkgReference.loads(args.package_reference)
    except (ConanException, InvalidNameException):
        raise ConanException(f"{args.package_reference} is not a valid package reference,"
                             f" provide a reference in the form "
                             f"name/version[@user/channel]#RECIPE_REVISION:PACKAGE_ID")
    if pref.revision:
        raise ConanException(f"Cannot list the revisions of a specific package revision")

    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not args.remote:
        result = CommandResult()
        try:
            result.elements = conan_api.list.package_revisions(pref)
        except NotFoundException:
            result.elements = []
        except Exception as e:
            result.error = str(e)

        results.append(result)

    if args.remote:
        remotes = get_remote_selection(conan_api, args.remote)
        for remote in remotes:
            result = CommandResult(remote=remote)
            try:
                result.elements = conan_api.list.package_revisions(pref, remote=remote)
            except NotFoundException:
                result.elements = []
            except Exception as e:
                result.error = str(e)
            results.append(result)

    print_list_package_revisions(results)
    return results


@conan_subcommand(formatters={"json": json_formatter})
def list_packages(conan_api, parser, subparser, *args):
    """
    List all the package IDs for a given recipe reference. If the reference doesn't
    include the recipe revision, the command will retrieve all the package IDs for
    the most recent revision.
    """
    subparser.add_argument("reference", help="Recipe reference or revision, e.g., libyaml/0.2.5 or "
                                             "libyaml/0.2.5#80b7cbe095ac7f38844b6511e69e453a")
    _add_remotes_and_cache_options(subparser)
    args = parser.parse_args(*args)

    try:
        ref = RecipeReference.loads(args.reference)
    except (ConanException, InvalidNameException):
        raise ConanException(f"{args.reference} is not a valid recipe reference, provide a reference"
                             f" in the form name/version[@user/channel][#RECIPE_REVISION]")

    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not args.remote:
        result = CommandResult()
        try:
            # This resolves "latest" or no revision
            refs = conan_api.search.recipe_revisions(args.reference, args.remote)
            if len(refs) == 0:
                raise ConanException("There are no recipes matching the expression '{}'"
                                     "".format(args.reference))
            if len(refs) > 1:
                raise ConanException("The expression '{}' resolved more "
                                     "than one recipe".format(args.reference))
            result.elements = conan_api.list.packages_configurations(refs[0])
        except Exception as e:
            result.error = str(e)
        results.append(result)

    if args.remote:
        remotes = get_remote_selection(conan_api, args.remote)
        for remote in remotes:
            result = CommandResult(remote=remote)
            try:
                result.elements = conan_api.list.packages_configurations(ref, remote=remote)
            except NotFoundException:
                result.elements = []
            except Exception as e:
                result.error = str(e)
            results.append(result)

    print_list_package_ids(results)
    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args):
    """
    Gets information about a recipe or package reference
    """
