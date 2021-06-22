import json

from conans.cli.cli import cli_out_write
from conans.client.output import Color
from conans.cli.command import conan_command, Extender


def print_output(info, show_colors):
    if info["error"]:
        # TODO: Handle errors
        return

    if "results" not in info or not info["results"]:
        return

    multiple_remotes = len(info["results"]) > 1
    indentation = 2 if multiple_remotes else 0
    remote_color = Color.BRIGHT_BLUE if show_colors else None
    recipe_color = Color.BRIGHT_WHITE if show_colors else None
    reference_color = Color.WHITE if show_colors else None

    for result in info["results"]:

        # We only show the name of the remotes if there are multiple remotes
        if multiple_remotes:
            cli_out_write("{}:".format(result["remote"]), remote_color)

        if "items" not in result or not result["items"]:
            cli_out_write("{}There are no matching recipes".format(" " * indentation))
            continue

        current_recipe = None
        for recipe in result["items"]:
            if recipe["recipe"]["name"] != current_recipe:
                current_recipe = recipe["recipe"]["name"]
                cli_out_write("{}{}".format(" " * indentation, current_recipe), recipe_color)

            reference = recipe["recipe"]["id"]
            cli_out_write("{}{}".format(" " * (indentation + 2), reference), reference_color)


def output_search_cli(info):
    print_output(info, show_colors=True)


def output_search_raw(info):
    print_output(info, show_colors=False)


def output_search_json(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


search_formatters = {
    "cli": output_search_cli,
    "raw": output_search_raw,
    "json": output_search_json
}


@conan_command(group="Consumer", formatters=search_formatters)
def search(conan_api, parser, *args, **kwargs):
    """
    Searches for package recipes whose name contain <query> in a remote or in the local cache
    """
    parser.add_argument("query",
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")
    parser.add_argument("-r", "--remote", default=None, action=Extender,
                        help="Remote to search. Accepts wildcards. To search in all remotes use *")
    args = parser.parse_args(*args)

    remotes = conan_api.get_active_remotes(args.remote)
    results = conan_api.search_recipes(remotes, args.query)
    return results
