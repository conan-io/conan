import json

from conan.api.conan_api import ConanAPI
from conan.api.output import Color, cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.cli.formatters.list import list_packages_html
from conan.internal.api.select_pattern import ListPattern


def print_serial(item, indent=None, color_index=None):
    indent = "" if indent is None else (indent + "  ")
    color_index = 0 if color_index is None else (color_index + 1)
    color_array = [Color.BRIGHT_BLUE, Color.GREEN, Color.BRIGHT_WHITE,
                   Color.BRIGHT_YELLOW, Color.CYAN, Color.WHITE]
    color = color_array[color_index % len(color_array)]
    if isinstance(item, dict):
        for k, v in item.items():
            cli_out_write(f"{indent}{k}", fg=color)
            print_serial(v, indent, color_index)
    elif item:
        color = Color.BRIGHT_RED if "ERROR:" in item else color
        cli_out_write(f"{indent}{item}", fg=color)


def print_list_text(results):
    """ Do litte format modification to serialized
    list bundle so it looks prettier on text output
    """
    info = results["results"]
    info = {remote: "There are no matching recipe references" if not values else values
            for remote, values in info.items()}
    info = {remote: f"ERROR: {values.get('error')}" if values.get("error") else values
            for remote, values in info.items()}

    def transform_text_serial(item):
        if isinstance(item, dict):
            result = {}
            for k, v in item.items():
                if isinstance(v, dict) and v.get("timestamp"):
                    timestamp = v.pop("timestamp")
                    k = f"{k} ({timestamp})"
                result[k] = transform_text_serial(v)
            return result
        return item
    info = {remote: transform_text_serial(values) for remote, values in info.items()}
    print_serial(info)


def print_list_json(data):
    results = data["results"]
    myjson = json.dumps(results, indent=4)
    cli_out_write(myjson)


@conan_command(group="Creator", formatters={"text": print_list_text,
                                            "json": print_list_json,
                                            "html": list_packages_html})
def list(conan_api: ConanAPI, parser, *args):
    """
    Lists existing recipes, revisions or packages in the cache or in remotes given a complete
    reference or a pattern.
    """
    parser.add_argument('reference', help="Recipe reference or package reference. "
                                          "Both can contain * as wildcard at any reference field. "
                                          "If revision is not specified, it is assumed latest one.")
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Only list packages matching a specific query. e.g: os=Windows AND "
                             "(arch=x86 OR compiler=gcc)")
    parser.add_argument("-r", "--remote", default=None, action="append",
                        help="Remote names. Accepts wildcards")
    parser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")

    args = parser.parse_args(*args)
    ref_pattern = ListPattern(args.reference)
    # If neither remote nor cache are defined, show results only from cache
    remotes = []
    if args.cache or not args.remote:
        remotes.append(None)
    if args.remote:
        remotes.extend(conan_api.remotes.list(args.remote))
    results = {}
    for remote in remotes:
        name = getattr(remote, "name", "Local Cache")
        try:
            list_bundle = conan_api.list.select(ref_pattern, args.package_query, remote)
        except Exception as e:
            results[name] = {"error": str(e)}
        else:
            results[name] = list_bundle.serialize()

    return {
        "results": results,
        "search_mode": ref_pattern.mode,
        "conan_api": conan_api
    }
