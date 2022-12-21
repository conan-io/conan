from collections import OrderedDict

from conan.api.conan_api import ConanAPI
from conan.api.output import Color, cli_out_write
from conan.cli.command import conan_command
from conan.cli.commands import default_json_formatter
# FIXME: "conan search" == "conan list recipes -r="*" -c" --> implement @conan_alias_command??
from conans.errors import ConanException

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def print_list_recipes(results):
    for remote, result in results.items():
        cli_out_write(f"{remote}:", fg=remote_color)
        if result.get("error"):
            cli_out_write(f"  ERROR: {result.get('error')}", fg=error_color)
        else:
            recipes = result.get("recipes", [])
            if not recipes:
                # FIXME: this should be an error message, NOT FOUND
                cli_out_write("  There are no matching recipe references")
            else:
                current_recipe = None
                for ref in recipes:
                    if ref.name != current_recipe:
                        current_recipe = ref.name
                        cli_out_write(f"  {current_recipe}", fg=recipe_color)

                    cli_out_write(f"    {ref}", fg=reference_color)


@conan_command(group="Consumer", formatters={"text": print_list_recipes,
                                             "json": default_json_formatter})
def search(conan_api: ConanAPI, parser, *args):
    """
    Searches for package recipes in a remote or remotes
    """
    parser.add_argument("query",
                        help="Search query to find package recipe reference, e.g., 'boost', 'lib*'")
    parser.add_argument("-r", "--remote", action="append",
                        help="Remote names. Accepts wildcards. If not specified it searches "
                             "in all remotes")
    args = parser.parse_args(*args)

    remotes = conan_api.remotes.list(args.remote)
    if not remotes:
        raise ConanException("There are no remotes to search from")

    results = OrderedDict()
    for remote in remotes:
        name = getattr(remote, "name", None)
        try:
            results[name] = {"recipes": conan_api.search.recipes(args.query, remote)}
        except Exception as e:
            results[name] = {"error": str(e)}
    return results
