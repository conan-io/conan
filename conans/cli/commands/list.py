import json

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.output import cli_out_write
from conans.client.output import Color
from conans.errors import ConanException, InvalidNameException
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.dates import from_timestamp_to_iso8601

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
values_color = Color.CYAN


def _print_common_headers(result, ref_type):
    if result.get("remote"):
        cli_out_write(f"{result['remote']}:", fg=remote_color)
    else:
        cli_out_write("Local Cache:", remote_color)

    if result.get("error"):
        cli_out_write(f"ERROR: {result['error']}", fg=error_color, indentation=2)
    elif not result.get("results"):
        cli_out_write(f"There are no matching {ref_type}", indentation=2)


def list_recipes_cli_formatter(results):
    for result in results:
        _print_common_headers(result, "recipe references")
        current_recipe = None
        for recipe in result["results"]:
            if recipe["name"] != current_recipe:
                current_recipe = recipe["name"]
                cli_out_write(current_recipe, fg=recipe_color, indentation=2)

            reference = recipe["id"]
            cli_out_write(reference, fg=reference_color, indentation=4)


def _list_revisions_cli_formatter(results, ref_type):
    for result in results:
        _print_common_headers(result, ref_type)
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
        _print_common_headers(result, "recipe references")
        reference = result["reference"]
        for pkg_id, props in result["results"].items():
            cli_out_write(repr(PackageReference(reference, pkg_id)),
                          fg=reference_color, indentation=2)
            for prop_name, values in props.items():
                if not values:
                    continue
                elif prop_name in requires_fields:
                    cli_out_write("requires:", fg=field_color, indentation=4)
                    for req in values:
                        cli_out_write(req, fg=values_color, indentation=6)
                elif prop_name in general_fields:
                    cli_out_write(f"{prop_name}:", fg=field_color, indentation=4)
                    for name, val in values.items():
                        cli_out_write(f"{name}={val}", fg=values_color, indentation=6)


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
    error = None
    if args.all_remotes:
        remotes, error = conan_api.get_active_remotes(None)
    elif args.remote:
        remotes, error = conan_api.get_active_remotes(args.remote)
    if error:
        raise ConanException(error)
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
        result, error = conan_api.search_local_recipes(args.query)
        results.append({
            "error": error,
            "results": result or []
        })
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result, error = conan_api.search_remote_recipes(args.query, remote)
            results.append({
                "remote": remote.name,
                "error": error,
                "results": result or []
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
        result, error = conan_api.get_recipe_revisions(args.reference)
        results.append({
            "reference": repr(ref),
            "error": error,
            "results": result or []
        })
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result, error = conan_api.get_recipe_revisions(ref, remote=remote)
            results.append({
                "reference": repr(ref),
                "remote": remote.name,
                "error": error,
                "results": result or []
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
        raise ConanException(f"{args.package_reference} is not a valid recipe revision reference,"
                             f" provide a reference in the form "
                             f"name/version[@user/channel]#RECIPE_REVISION:PACKAGE_ID")
    if pref.revision:
        raise ConanException(f"Cannot list the revisions of a specific package revision")

    use_remotes = any([args.remote, args.all_remotes])
    results = []
    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        result, error = conan_api.get_package_revisions(pref)
        results.append({
            "reference": repr(pref),
            "error": error,
            "results": result or []
        })
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result, error = conan_api.get_package_revisions(pref, remote=remote)
            results.append({
                "reference": repr(pref),
                "remote": remote.name,
                "error": error,
                "results": result or []
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
        result, error = conan_api.get_package_ids(ref)
        result = result or {}
        ret = {
            "error": error
        }
        ret.update(result)
        results.append(ret)
    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result, error = conan_api.get_package_ids(ref, remote=remote)
            result = result or {}
            ret = {
                "remote": remote.name,
                "error": error
            }
            ret.update(result)
            results.append(ret)

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args, **kwargs):
    """
    Gets information about a recipe or package reference
    """
