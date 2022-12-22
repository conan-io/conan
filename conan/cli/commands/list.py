import json

from conan.api.conan_api import ConanAPI
from conan.api.output import Color, cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.cli.commands import ConanJSONEncoder
from conan.cli.formatters.list import list_packages_html
from conan.internal.api.select_pattern import ListPattern
from conans.util.dates import timestamp_to_str

remote_color = Color.BRIGHT_BLUE
recipe_name_color = Color.GREEN
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def print_list_text(results):
    results = results["results"]

    for remote, refs in results.items():
        cli_out_write(f"{remote}:", fg=remote_color)

        if refs.get("error"):
            cli_out_write(f"  ERROR: {refs.get('error')}", fg=error_color)
            continue

        if not refs:
            cli_out_write(f"  There are no matching recipe references", fg=recipe_color)
            continue

        showed_ref_names = []
        indentation = "  "
        for ref, prefs in refs.items():
            ref_name = ref.name
            if ref_name not in showed_ref_names:
                showed_ref_names.append(ref_name)
                cli_out_write(f"{indentation}{ref_name}", fg=recipe_name_color)
            cli_out_write(f"{indentation * 2}{ref.repr_humantime() if ref.timestamp else ref}",
                          fg=recipe_color)
            if prefs:
                for pref, binary_info in prefs:
                    pref_date = f" ({timestamp_to_str(pref.timestamp)})" if pref.timestamp else ""
                    cli_out_write(f"{indentation * 3}PID: {pref.package_id}{pref_date}",
                                  fg=reference_color)
                    if not binary_info and pref.revision:
                        cli_out_write(f"{indentation * 4}PREV: {pref.revision}", fg=field_color)
                        continue
                    elif not binary_info:
                        cli_out_write(f"{indentation * 4}No package info/revision was found.",
                                      fg=field_color)
                        continue
                    for item, contents in binary_info.items():
                        if not contents:
                            continue
                        cli_out_write(f"{indentation * 4}{item}:", fg=field_color)
                        if isinstance(contents, dict):
                            for k, v in contents.items():
                                cli_out_write(f"{indentation * 5}{k}={v}", fg=value_color)
                        else:
                            for c in contents:
                                cli_out_write(f"{indentation * 5}{c}", fg=value_color)


def print_list_json(data):
    results = data["results"]
    myjson = json.dumps(results, indent=4, cls=ConanJSONEncoder)
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
    # If neither remote nor cache are defined, show results only from cache
    remotes = []
    if args.cache or not args.remote:
        remotes.append(None)
    if args.remote:
        remotes.extend(conan_api.remotes.list(args.remote))
    results = {}
    for remote in remotes:
        name = getattr(remote, "name", "Local Cache")
        ref_pattern = ListPattern(args.reference)
        try:
            list_bundle = conan_api.list.select(ref_pattern, args.package_query, remote)
        except Exception as e:
            results[name] = {"error": str(e)}
        else:
            results[name] = list_bundle.serialize() if args.format in ("json", "html") \
                else list_bundle.recipes
    return {
        "results": results,
        "conan_api": conan_api
    }
