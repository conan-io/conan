import json

from conans.cli.output import cli_out_write
from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.client.output import Color
from conans.util.dates import iso8601_to_str

indentation = 2
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
            cli_out_write("{}:".format(remote_results["remote"]), remote_color)

        if not remote_results.get("results"):
            cli_out_write("{}There are no matching recipes".format(" " * indentation))

        current_recipe = None
        for recipe in remote_results["results"]:
            if recipe["name"] != current_recipe:
                current_recipe = recipe["name"]
                cli_out_write("{}{}".format(" " * indentation, current_recipe), recipe_color)

            reference = recipe["id"]
            cli_out_write("{}{}".format(" " * (indentation * 2), reference), reference_color)


def list_recipe_revisions_cli_formatter(results):
    for remote_results in results:
        if remote_results.get("error"):
            # TODO: Handle errors
            return

        if not remote_results.get("remote"):
            cli_out_write("Local Cache:", remote_color)
        else:
            cli_out_write("{}:".format(remote_results["remote"]), remote_color)

        if not remote_results.get("results"):
            cli_out_write("{}There are no matching recipes".format(" " * indentation))

        reference = remote_results["reference"]
        for revisions in remote_results["results"]:
            cli_out_write(
                "{}{}#{} ({})".format(
                    " " * indentation,
                    reference,
                    revisions["revision"],
                    iso8601_to_str(revisions["time"])
                ),
                recipe_color
            )


def list_package_revisions_cli_formatter(results):
    for remote_results in results:
        if remote_results.get("error"):
            # TODO: Handle errors
            return

        if not remote_results.get("remote"):
            cli_out_write("Local Cache:", remote_color)
        else:
            cli_out_write("{}:".format(remote_results["remote"]), remote_color)

        if not remote_results.get("results"):
            cli_out_write("{}There are no matching recipes".format(" " * indentation))

        reference = remote_results["package_reference"]
        for revisions in remote_results["results"]:
            cli_out_write(
                "{}{}#{} ({})".format(
                    " " * indentation,
                    reference,
                    revisions["revision"],
                    iso8601_to_str(revisions["time"])
                ),
                recipe_color
            )


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

    remotes = None
    if args.all_remotes:
        remotes = conan_api.get_active_remotes(None)
    elif args.remote:
        remotes = conan_api.get_active_remotes(args.remote)

    results = []
    if args.cache:
        result = {
            'remote': None,
            'reference': args.reference,
            'results': conan_api.get_local_recipe_revisions(args.reference)
        }
        results.append(result)
    if remotes:
        for remote in remotes:
            result = {
                'remote': remote.name,
                'reference': args.reference,
                'results': conan_api.get_remote_recipe_revisions(args.reference, remote=remote)
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

    remotes = None
    if args.all_remotes:
        remotes = conan_api.get_active_remotes(None)
    elif args.remote:
        remotes = conan_api.get_active_remotes(args.remote)

    results = []
    if args.cache:
        result = {
            'remote': None,
            'package_reference': args.package_reference,
            'results': conan_api.get_local_package_revisions(args.package_reference)
        }
        results.append(result)
    if remotes:
        for remote in remotes:
            result = {
                'remote': remote.name,
                'package_reference': args.package_reference,
                'results': conan_api.get_remote_package_revisions(args.package_reference,
                                                                  remote=remote)
            }
            results.append(result)

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args, **kwargs):
    """
    Gets information about a recipe or package
    """
