import json

from conans.cli.output import cli_out_write
from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.client.output import Color


def list_recipes_cli_formatter(info):
    indentation = 2
    remote_color = Color.BRIGHT_BLUE
    recipe_color = Color.BRIGHT_WHITE
    reference_color = Color.WHITE

    for results in info:
        if results["error"]:
            # TODO: Handle errors
            return

        if "remote" not in results or not results["remote"]:
            cli_out_write("Local Cache:", remote_color)
        else:
            cli_out_write("{}:".format(results["remote"]), remote_color)

        if "results" not in results or not results["results"]:
            cli_out_write("{}There are no matching recipes".format(" " * indentation))

        current_recipe = None
        for recipe in results["results"]:
            if recipe["name"] != current_recipe:
                current_recipe = recipe["name"]
                cli_out_write("{}{}".format(" " * indentation, current_recipe), recipe_color)

            reference = recipe["id"]
            cli_out_write("{}{}".format(" " * (indentation * 2), reference), reference_color)


def list_recipes_json_formatter(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


list_recipes_formatters = {
    "cli": list_recipes_cli_formatter,
    "json": list_recipes_json_formatter
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
            results.append(conan_api.search_remote_recipes(remote, args.query))

    return results


@conan_command(group=COMMAND_GROUPS['consumer'])
def list(conan_api, parser, *args, **kwargs):
    """
    Gets information about a recipe or package
    """
