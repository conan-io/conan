import json

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.output import cli_out_write
from conans.client.output import Color
from conans.errors import ConanException, InvalidNameException, PackageNotFoundException, \
    NotFoundException
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.dates import from_timestamp_to_iso8601

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def _print_common_headers(result):
    if result.get("remote"):
        cli_out_write(f"{result['remote']}:", fg=remote_color)
    else:
        cli_out_write("Local Cache:", remote_color)


def list_recipes_cli_formatter(results):
    for result in results:
        _print_common_headers(result)
        if result.get("error"):
            error = f"ERROR: {result['error']}"
            cli_out_write(error, fg=error_color, indentation=2)
            continue
        elif not result.get("results"):
            cli_out_write("There are no matching recipe references", indentation=2)
            continue
        current_recipe = None
        for recipe in result["results"]:
            if recipe["name"] != current_recipe:
                current_recipe = recipe["name"]
                cli_out_write(current_recipe, fg=recipe_color, indentation=2)

            reference = recipe["id"]
            cli_out_write(reference, fg=reference_color, indentation=4)


def _list_revisions_cli_formatter(results, ref_type):
    for result in results:
        _print_common_headers(result)
        if result.get("error"):
            error = f"ERROR: {result['error']}"
            cli_out_write(error, fg=error_color, indentation=2)
            continue
        elif not result.get("results"):
            cli_out_write(f"There are no matching {ref_type}", indentation=2)
            continue
        reference = result["reference"]
        for revisions in result["results"]:
            rev = revisions["revision"]
            date = from_timestamp_to_iso8601(revisions["time"])
            cli_out_write(f"{reference}#{rev} ({date})", fg=recipe_color, indentation=2)


def list_recipe_revisions_cli_formatter(results):
    _list_revisions_cli_formatter(results, "recipe references")


def list_package_revisions_cli_formatter(results):
    _list_revisions_cli_formatter(results, "package references")


def list_package_ids_cli_formatter(results):
    # Artifactory uses field 'requires', conan_center 'full_requires'
    requires_fields = ("requires", "full_requires")
    general_fields = ("options", "settings")

    for result in results:
        _print_common_headers(result)
        if result.get("error"):
            error = f"ERROR: {result['error']}"
            cli_out_write(error, fg=error_color, indentation=2)
            continue
        elif not result.get("results"):
            cli_out_write("There are no matching recipe references", indentation=2)
            continue
        reference = result["reference"]
        for pkg_id, props in result["results"].items():
            cli_out_write(f"{reference}:{pkg_id}",
                          fg=reference_color, indentation=2)
            for prop_name, values in props.items():
                if not values:
                    continue
                elif prop_name in requires_fields:
                    cli_out_write("requires:", fg=field_color, indentation=4)
                    for req in values:
                        cli_out_write(req, fg=value_color, indentation=6)
                elif prop_name in general_fields:
                    cli_out_write(f"{prop_name}:", fg=field_color, indentation=4)
                    for name, val in values.items():
                        cli_out_write(f"{name}={val}", fg=value_color, indentation=6)


# FIXME: it's a general formatter, perhaps we should look for another module
def json_formatter(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


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
                               help="Name of the remote to add")
    remotes_group.add_argument("-a", "--all-remotes", action='store_true',
                               help="Search in all the remotes")
    subparser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")


def _get_remotes(conan_api, args):
    remotes = []
    if args.all_remotes:
        remotes = conan_api.get_active_remotes(None)
    elif args.remote:
        remotes = conan_api.get_active_remotes(args.remote)
    return remotes


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

    use_remotes = any([args.remote, args.all_remotes])
    results = []

    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        error = None
        try:
            result = conan_api.search_local_recipes(args.query)
        except Exception as e:
            error = str(e)
            result = []

        results.append({
            "error": error,
            "results": result
        })
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            error = None
            try:
                result = conan_api.search_remote_recipes(args.query, remote)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                result = []
            except Exception as e:
                error = str(e)
                result = []

            results.append({
                "remote": remote.name,
                "error": error,
                "results": result
            })
    return results


@conan_subcommand(formatters=list_recipe_revisions_formatters)
def list_recipe_revisions(conan_api, parser, subparser, *args):
    """
    List all the revisions of a recipe reference.
    """
    subparser.add_argument("reference", help="Recipe reference, e.g., libyaml/0.2.5")
    _add_remotes_and_cache_options(subparser)
    args = parser.parse_args(*args)

    try:
        ref = ConanFileReference.loads(args.reference)
    except (ConanException, InvalidNameException):
        raise ConanException(f"{args.reference} is not a valid recipe reference, provide a reference"
                             f" in the form name/version[@user/channel]")
    if ref.revision:
        raise ConanException(f"Cannot list the revisions of a specific recipe revision")

    use_remotes = any([args.remote, args.all_remotes])
    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        error = None
        try:
            result = conan_api.get_recipe_revisions(ref)
        except Exception as e:
            error = str(e)
            result = []

        results.append({
            "reference": repr(ref),
            "error": error,
            "results": result
        })
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            error = None
            try:
                result = conan_api.get_recipe_revisions(ref, remote=remote)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                result = []
            except Exception as e:
                error = str(e)
                result = []

            results.append({
                "reference": repr(ref),
                "remote": remote.name,
                "error": error,
                "results": result
            })

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
        pref = PackageReference.loads(args.package_reference)
    except (ConanException, InvalidNameException):
        raise ConanException(f"{args.package_reference} is not a valid package reference,"
                             f" provide a reference in the form "
                             f"name/version[@user/channel]#RECIPE_REVISION:PACKAGE_ID")
    if pref.revision:
        raise ConanException(f"Cannot list the revisions of a specific package revision")

    use_remotes = any([args.remote, args.all_remotes])
    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        error = None
        try:
            result = conan_api.get_package_revisions(pref)
        except Exception as e:
            error = str(e)
            result = []

        results.append({
            "reference": repr(pref),
            "error": error,
            "results": result
        })
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            error = None
            try:
                result = conan_api.get_package_revisions(pref, remote=remote)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                result = []
            except Exception as e:
                error = str(e)
                result = []

            results.append({
                "reference": repr(pref),
                "remote": remote.name,
                "error": error,
                "results": result
            })

    return results


@conan_subcommand(formatters=list_package_ids_formatters)
def list_package_ids(conan_api, parser, subparser, *args):
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
        ref = ConanFileReference.loads(args.reference)
    except (ConanException, InvalidNameException):
        raise ConanException(f"{args.reference} is not a valid recipe reference, provide a reference"
                             f" in the form name/version[@user/channel][#RECIPE_REVISION]")

    use_remotes = any([args.remote, args.all_remotes])
    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        error = None
        try:
            result = conan_api.get_package_ids(ref)
        except Exception as e:
            error = str(e)
            result = {}

        result["error"] = error
        results.append(result)

    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            error = None
            try:
                result = conan_api.get_package_ids(ref, remote=remote)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                result = {}
            except Exception as e:
                error = str(e)
                result = {}

            result.update({
                "remote": remote.name,
                "error": error
            })
            results.append(result)

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args, **kwargs):
    """
    Gets information about a recipe or package reference
    """
