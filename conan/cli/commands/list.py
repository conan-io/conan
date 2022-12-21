from conan.api.conan_api import ConanAPI
from conan.api.output import Color, cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.internal.api.select_pattern import ListPattern

remote_color = Color.BRIGHT_BLUE
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def print_list_results(results):
    results = results["results"]
    for remote, refs in results.items():
        cli_out_write(f"{remote}", fg=remote_color)
        for ref, prefs in refs.items():
            cli_out_write(f"  {ref}", fg=value_color)
            if prefs:
                for pref, binary_info in prefs:
                    cli_out_write(f"    {pref.repr_notime()}", fg=reference_color)
                    if binary_info is None:
                        continue
                    for item, contents in binary_info.items():
                        if not contents:
                            continue
                        cli_out_write(f"      {item}:", fg=field_color)
                        if isinstance(contents, dict):
                            for k, v in contents.items():
                                cli_out_write(f"        {k}={v}", fg=value_color)
                        else:
                            for c in contents:
                                cli_out_write(f"        {c}", fg=value_color)


@conan_command(group="Creator", formatters={"text": print_list_results})
def list(conan_api: ConanAPI, parser, *args):
    """
    List existing recipes, revisions or packages in the cache or in remotes given a complete
    reference or a pattern.
    """
    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as "
                                          "wildcard at any reference field. If revision is not "
                                          "specified, it is assumed latest one.")
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
        # Get all the package revisions (if only_revs is True, then only the recipe revisions)
        list_bundle = conan_api.list.select(ref_pattern, args.package_query, remote)
        results[name] = list_bundle.serialize()
    return {
        "results": results,
        "conan_api": conan_api
    }
