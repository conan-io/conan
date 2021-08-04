import json

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.output import cli_out_write
from conans.client.output import Color
from conans.util.dates import from_timestamp_to_iso8601
from conans.model.ref import PackageReference

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED


def _print_common_headers(result, ref_type):
    if result.get("remote"):
        cli_out_write(f"{result['remote']}:", fg=remote_color)
    else:
        cli_out_write("Local Cache:", remote_color)

    if result.get("error"):
        cli_out_write(result["error"], fg=error_color, indentation=2)

    if not result.get("results"):
        cli_out_write(f"There are no matching {ref_type}", indentation=2)


def list_recipes_cli_formatter(results):
    for result in results:
        _print_common_headers(result, "recipes")
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
    _list_revisions_cli_formatter(results, "recipes")


def list_package_revisions_cli_formatter(results):
    _list_revisions_cli_formatter(results, "packages")


def list_package_ids_cli_formatter(results):
    # Artifactory uses field 'requires', conan_center 'full_requires'
    requires_fields = ("requires", "full_requires")
    general_fields = ("options", "settings")

    for result in results:
        _print_common_headers(result, "references")
        reference = result["reference"]
        for pkg_id, props in result["results"].items():
            cli_out_write(repr(PackageReference(reference, pkg_id)),
                          fg=reference_color, indentation=2)
            for prop_name, values in props.items():
                if not values:
                    continue
                elif prop_name in requires_fields:
                    cli_out_write("requires:", fg=Color.BRIGHT_YELLOW, indentation=4)
                    for req in values:
                        cli_out_write(req, fg=Color.CYAN, indentation=6)
                elif prop_name in general_fields:
                    cli_out_write(f"{prop_name}:", fg=Color.BRIGHT_YELLOW, indentation=4)
                    for name, val in values.items():
                        cli_out_write(f"{name}={val}", fg=Color.CYAN, indentation=6)


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


@conan_subcommand(formatters=list_recipes_formatters)
def list_recipes(conan_api, parser, subparser, *args):
    """
    Search available recipes in the local cache or in the remotes
    """
    subparser.add_argument(
        "query",
        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'"
    )
    remotes_group = subparser.add_mutually_exclusive_group()
    remotes_group.add_argument("-r", "--remote", default=None, action=Extender,
                           help="Name of the remote to add")
    remotes_group.add_argument("-a", "--all-remotes", action='store_true',
                           help="Search in all the remotes")
    subparser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")
    args = parser.parse_args(*args)

    if not args.cache and not args.remote and not args.all_remotes:
        # If neither remote nor cache are defined, show results only from cache
        args.cache = True

    remotes = None
    if args.all_remotes:
        remotes = conan_api.get_active_remotes(None)
    elif args.remote:
        remotes = conan_api.get_active_remotes(args.remote)

    results = []
    if args.cache:
        results.append(conan_api.search_local_recipes(args.query))
    if remotes:
        for remote in remotes:
            results.append(conan_api.search_remote_recipes(args.query, remote))

    return results


def _add_common_list_subcommands(subparser, positional_arg_name):
    subparser.add_argument(positional_arg_name)
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


@conan_subcommand(formatters=list_recipe_revisions_formatters)
def list_recipe_revisions(conan_api, parser, subparser, *args):
    """
    List all the revisions of a recipe reference.
    """
    _add_common_list_subcommands(subparser, "reference")
    args = parser.parse_args(*args)

    use_remotes = any([args.remote, args.all_remotes])
    results = []

    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        result = conan_api.get_recipe_revisions(args.reference)
        results.append(result)

    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result = conan_api.get_recipe_revisions(args.reference, remote=remote)
            results.append(result)

    return results


@conan_subcommand(formatters=list_package_revisions_formatters)
def list_package_revisions(conan_api, parser, subparser, *args):
    """
    List all the revisions of a package ID reference.
    """
    _add_common_list_subcommands(subparser, "package_reference")
    args = parser.parse_args(*args)

    use_remotes = any([args.remote, args.all_remotes])
    results = []

    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        result = conan_api.get_package_revisions(args.package_reference)
        results.append(result)

    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result = conan_api.get_package_revisions(args.package_reference, remote=remote)
            results.append(result)

    return results


@conan_subcommand(formatters=list_package_ids_formatters)
def list_package_ids(conan_api, parser, subparser, *args):
    """
    List all the package IDs for a given recipe reference. If the reference doesn't
    include the recipe revision, the command will retrieve all the package IDs for
    the most recent revision.
    """
    _add_common_list_subcommands(subparser, "reference")
    args = parser.parse_args(*args)

    use_remotes = any([args.remote, args.all_remotes])
    results = []

    # If neither remote nor cache are defined, show results only from cache
    if args.cache or not use_remotes:
        result = conan_api.get_package_ids(args.reference)
        results.append(result)

    if use_remotes:
        remotes = _get_remotes(conan_api, args)
        for remote in remotes:
            result = conan_api.get_package_ids(args.reference, remote=remote)
            results.append(result)

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args, **kwargs):
    """
    Gets information about a recipe or package
    """
