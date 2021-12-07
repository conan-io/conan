import copy
from typing import List

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.commands import json_formatter, CommandResult
from conans.cli.common import get_remote_selection
from conans.cli.output import Color
from conans.cli.output import cli_out_write
from conans.errors import ConanException, InvalidNameException, PackageNotFoundException, \
    NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.dates import from_timestamp_to_iso8601

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def _print_common_headers(result: CommandResult):
    if result.remote:
        cli_out_write(f"{result.remote.name}:", fg=remote_color)
    else:
        cli_out_write("Local Cache:", remote_color)


def list_recipes_cli_formatter(results: List[CommandResult]):
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"ERROR: {result.error}"
            cli_out_write(error, fg=error_color, indentation=2)
        elif not result.elements:
            cli_out_write("There are no matching recipe references", indentation=2)
        else:
            current_recipe = None
            for ref in result.elements:
                if ref.name != current_recipe:
                    current_recipe = ref.name
                    cli_out_write(current_recipe, fg=recipe_color, indentation=2)

                cli_out_write(ref, fg=reference_color, indentation=4)


def list_recipe_revisions_cli_formatter(results):
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"ERROR: {result.error}"
            cli_out_write(error, fg=error_color, indentation=2)
        elif not result.elements:
            cli_out_write(f"There are no matching recipe references", indentation=2)
        else:
            for ref in result.elements:
                date = from_timestamp_to_iso8601(ref.timestamp)
                cli_out_write(f"{ref.repr_notime()} ({date})", fg=recipe_color, indentation=2)


def list_package_revisions_cli_formatter(results):
    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"ERROR: {result.error}"
            cli_out_write(error, fg=error_color, indentation=2)
        elif not result.elements:
            cli_out_write(f"There are no matching package references", indentation=2)
        else:
            for pref in result.elements:
                date = from_timestamp_to_iso8601(pref.timestamp)
                cli_out_write(f"{pref.repr_notime()} ({date})", fg=recipe_color, indentation=2)


def list_package_ids_cli_formatter(results: List[CommandResult]):

    for result in results:
        _print_common_headers(result)
        if result.error:
            error = f"ERROR: {result.error}"
            cli_out_write(error, fg=error_color, indentation=2)
        elif not result.elements:
            cli_out_write("There are no packages", indentation=2)
        else:
            for pref, search_info in result.elements.items():
                _tmp_pref = copy.copy(pref)
                _tmp_pref.revision = None  # Do not show the revision of the package
                cli_out_write(f"{_tmp_pref.repr_notime()}", fg=reference_color, indentation=2)
                if search_info.requires:
                    cli_out_write("requires:", fg=field_color, indentation=4)
                    for req in search_info.requires:
                        cli_out_write(req, fg=value_color, indentation=6)
                if search_info.settings:
                    cli_out_write(f"settings:", fg=field_color, indentation=4)
                    for name, val in search_info.settings.items():
                        cli_out_write(f"{name}={val}", fg=value_color, indentation=6)
                if search_info.options:
                    cli_out_write(f"options:", fg=field_color, indentation=4)
                    for name, val in search_info.options.items():
                        cli_out_write(f"{name}={val}", fg=value_color, indentation=6)


list_recipes_formatters = {
    "cli": list_recipes_cli_formatter,
    "json": json_formatter
}
list_recipe_revisions_formatters = {
    "cli": list_recipe_revisions_cli_formatter,
    "json": json_formatter
}
list_package_revisions_formatters = {
    "cli": list_package_revisions_cli_formatter,
    "json": json_formatter
}
list_package_ids_formatters = {
    "cli": list_package_ids_cli_formatter,
    "json": json_formatter
}


def _add_remotes_and_cache_options(subparser):
    remotes_group = subparser.add_mutually_exclusive_group()
    remotes_group.add_argument("-r", "--remote", default=None, action=Extender,
                               help="Remote names. Accepts wildcards")
    subparser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")


@conan_subcommand(formatters=list_recipes_formatters)
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
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                pass
            except Exception as e:
                result.error = str(e)
            results.append(result)
    return results


@conan_subcommand(formatters=list_recipe_revisions_formatters)
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
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                pass
            except Exception as e:
                result.error = str(e)

            results.append(result)

    return results


@conan_subcommand(formatters=list_package_revisions_formatters)
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
        except Exception as e:
            result.error = str(e)

        results.append(result)

    if args.remote:
        remotes = get_remote_selection(conan_api, args.remote)
        for remote in remotes:
            result = CommandResult(remote=remote)
            try:
                result.elements = conan_api.list.package_revisions(pref, remote=remote)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                pass
            except Exception as e:
                result.error = str(e)
            results.append(result)
    return results


@conan_subcommand(formatters=list_package_ids_formatters)
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
            result.elements = conan_api.list.packages_configurations(ref)
        except Exception as e:
            result.error = str(e)
        results.append(result)

    if args.remote:
        remotes = get_remote_selection(conan_api, args.remote)
        for remote in remotes:
            result = CommandResult(remote=remote)
            try:
                result.elements = conan_api.list.packages_configurations(ref, remote=remote)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                pass
            except Exception as e:
                result.error = str(e)
            results.append(result)

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args):
    """
    Gets information about a recipe or package reference
    """
