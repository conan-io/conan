import json

from conans.cli.cli import cli_out_write
from conans.cli.command import conan_command, Extender, COMMAND_GROUPS
from conans.client.output import Color


def _output_search_cli(info):
    indentation = 2
    remote_color = Color.BRIGHT_BLUE
    recipe_color = Color.BRIGHT_WHITE
    reference_color = Color.WHITE

    for remote_results in info:
        if remote_results["error"]:
            # TODO: Handle errors
            return

        if "results" not in remote_results or not remote_results["results"]:
            return

        for result in remote_results["results"]:
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


def _output_search_json(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


search_formatters = {
    "cli": _output_search_cli,
    "json": _output_search_json
}


@conan_command(group=COMMAND_GROUPS['consumer'], formatters=search_formatters)
def search(conan_api, parser, *args, **kwargs):
    """
    Searches for package recipes in a remote or remotes
    """
    parser.add_argument("query",
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")
    parser.add_argument("-r", "--remote", default=None, action=Extender,
                        help="Remote to search. Accepts wildcards. To search in all remotes use *")
    args = parser.parse_args(*args)

    remotes = conan_api.get_active_remotes(args.remote)

    results = []
    for remote in remotes:
        results.append(conan_api.search_recipes(remote, args.query))
    return results
