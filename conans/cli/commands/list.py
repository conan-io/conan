import json

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.output import cli_out_write
from conans.client.output import Color
from conans.util.dates import iso8601_to_str

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE


def list_recipes_cli_formatter(results):
    for remote_results in results:
        if remote_results.get("error"):
            # TODO: Handle errors
            return

        if not remote_results.get("remote"):
            cli_out_write("Local Cache:", remote_color)
        else:
            cli_out_write(f"{remote_results['remote']}:", fg=remote_color)

        if not remote_results.get("results"):
            cli_out_write("There are no matching recipes", indentation=2)

        current_recipe = None
        for recipe in remote_results["results"]:
            if recipe["name"] != current_recipe:
                current_recipe = recipe["name"]
                cli_out_write(current_recipe, fg=recipe_color, indentation=2)

            reference = recipe["id"]
            cli_out_write(reference, fg=reference_color, indentation=2)


def _list_revisions_cli_formatter(results, is_package=False):
    for remote_results in results:
        if remote_results.get("error"):
            # TODO: Handle errors
            return

        if not remote_results.get("remote"):
            cli_out_write("Local Cache:", fg=remote_color)
        else:
            cli_out_write(f"{remote_results['remote']}:", fg=remote_color)

        if not remote_results.get("results"):
            ref_type = "packages" if is_package else "recipes"
            cli_out_write(f"There are no matching {ref_type}", indentation=2)

        reference = remote_results["package_reference" if is_package else "reference"]
        for revisions in remote_results["results"]:
            rev = revisions["revision"]
            date = iso8601_to_str(revisions["time"])
            cli_out_write(f"{reference}#{rev} ({date})", fg=recipe_color, indentation=2)


def list_recipe_revisions_cli_formatter(results):
    _list_revisions_cli_formatter(results)


def list_package_revisions_cli_formatter(results):
    _list_revisions_cli_formatter(results, is_package=True)


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
    List all the revisions of a recipe
    """
    _add_common_list_subcommands(subparser, "reference")
    args = parser.parse_args(*args)

    if not args.cache and not args.remote and not args.all_remotes:
        # If neither remote nor cache are defined, show results only from cache
        args.cache = True

    remotes = _get_remotes(conan_api, args)

    results = []
    if args.cache:
        result = {
            'remote': None,
            'reference': args.reference,
            'results': conan_api.get_recipe_revisions(args.reference)
        }
        results.append(result)

    for remote in remotes:
        result = {
            'remote': remote.name,
            'reference': args.reference,
            'results': conan_api.get_recipe_revisions(args.reference, remote=remote)
        }
        results.append(result)

    return results


@conan_subcommand(formatters=list_package_revisions_formatters)
def list_package_revisions(conan_api, parser, subparser, *args):
    """
    List all the revisions of a package ID
    """
    _add_common_list_subcommands(subparser, "package_reference")
    args = parser.parse_args(*args)

    if not args.cache and not args.remote and not args.all_remotes:
        # If neither remote nor cache are defined, show results only from cache
        args.cache = True

    remotes = _get_remotes(conan_api, args)

    results = []
    if args.cache:
        result = {
            'remote': None,
            'package_reference': args.package_reference,
            'results': conan_api.get_package_revisions(args.package_reference)
        }
        results.append(result)

    for remote in remotes:
        result = {
            'remote': remote.name,
            'package_reference': args.package_reference,
            'results': conan_api.get_package_revisions(args.package_reference, remote=remote)
        }
        results.append(result)

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args, **kwargs):
    """
    Gets information about a recipe or package
    """
