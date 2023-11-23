import json

from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern, MultiPackagesList
from conan.api.output import Color, cli_out_write
from conan.cli import make_abs_path
from conan.cli.command import conan_command, OnceArgument
from conan.cli.formatters.list import list_packages_html
from conans.errors import ConanException
from conans.util.dates import timestamp_to_str


# Keep them so we don't break other commands that import them, but TODO: Remove later
remote_color = Color.BRIGHT_BLUE
recipe_name_color = Color.GREEN
recipe_color = Color.BRIGHT_WHITE
reference_color = Color.WHITE
error_color = Color.BRIGHT_RED
field_color = Color.BRIGHT_YELLOW
value_color = Color.CYAN


def print_serial(item, indent=None, color_index=None):
    indent = "" if indent is None else (indent + "  ")
    color_index = 0 if color_index is None else (color_index + 1)
    color_array = [Color.BRIGHT_BLUE, Color.BRIGHT_GREEN, Color.BRIGHT_WHITE,
                   Color.BRIGHT_YELLOW, Color.BRIGHT_CYAN, Color.BRIGHT_MAGENTA, Color.WHITE]
    color = color_array[color_index % len(color_array)]
    if isinstance(item, dict):
        for k, v in item.items():
            if isinstance(v, str):
                if k.lower() == "error":
                    color = Color.BRIGHT_RED
                    k = "ERROR"
                elif k.lower() == "warning":
                    color = Color.BRIGHT_YELLOW
                    k = "WARN"
                cli_out_write(f"{indent}{k}: {v}", fg=color)
            else:
                cli_out_write(f"{indent}{k}", fg=color)
                print_serial(v, indent, color_index)
    elif isinstance(item, type([])):
        for elem in item:
            cli_out_write(f"{indent}{elem}", fg=color)
    elif item:
        cli_out_write(f"{indent}{item}", fg=color)


def print_list_text(results):
    """ Do litte format modification to serialized
    list bundle so it looks prettier on text output
    """
    info = results["results"]

    # Extract command single package name
    new_info = {}
    for remote, remote_info in info.items():
        new_remote_info = {}
        for ref, content in remote_info.items():
            if ref == "error":
                new_remote_info[ref] = content
            else:
                name, _ = ref.split("/", 1)
                new_remote_info.setdefault(name, {})[ref] = content
        new_info[remote] = new_remote_info
    info = new_info

    info = {remote: {"warning": "There are no matching recipe references"} if not values else values
            for remote, values in info.items()}

    def format_timestamps(item):
        if isinstance(item, dict):
            result = {}
            for k, v in item.items():
                if isinstance(v, dict) and v.get("timestamp"):
                    timestamp = v.pop("timestamp")
                    k = f"{k} ({timestamp_to_str(timestamp)})"
                result[k] = format_timestamps(v)
            return result
        return item
    info = {remote: format_timestamps(values) for remote, values in info.items()}
    print_serial(info)


def print_list_compact(results):
    info = results["results"]
    # Extract command single package name
    new_info = {}

    for remote, remote_info in info.items():
        if not remote_info or "error" in remote_info:
            new_info[remote] = {"warning": "There are no matching recipe references"}
            continue
        new_remote_info = {}
        for ref, ref_info in remote_info.items():
            new_ref_info = {}
            for rrev, rrev_info in ref_info.get("revisions", {}).items():
                new_rrev_info = {}
                new_rrev = f"{ref}#{rrev}"
                timestamp = rrev_info.get("timestamp")
                if timestamp:
                    new_rrev += f" ({timestamp_to_str(timestamp)})"
                # collect all options
                common_options = {}
                for pid, pid_info in rrev_info.get("packages", {}).items():
                    options = pid_info.get("info", {}).get("options", {})
                    common_options.update(options)
                for pid, pid_info in rrev_info.get("packages", {}).items():
                    options = pid_info.get("info", {}).get("options")
                    if options:  # If a package has no options, like header-only, skip
                        common_options = {k: v for k, v in common_options.items()
                                          if k in options and v == options[k]}
                for pid, pid_info in rrev_info.get("packages", {}).items():
                    options = pid_info.get("info", {}).get("options")
                    if options:
                        for k, v in options.items():
                            if v != common_options.get(k):
                                common_options.pop(k, None)
                # format options
                for pid, pid_info in rrev_info.get("packages", {}).items():
                    new_pid = f"{ref}#{rrev}:{pid}"
                    new_pid_info = {}
                    info = pid_info.get("info")
                    settings = info.get("settings")
                    if settings:  # A bit of pretty order, first OS-ARCH
                        values = [settings.pop(s, None)
                                  for s in ("os", "arch", "build_type", "compiler")]
                        values = [v for v in values if v is not None]
                        values.extend(settings.values())
                        new_pid_info["settings"] = ", ".join(values)
                    options = info.get("options")
                    if options:
                        diff_options = {k: v for k, v in options.items() if k not in common_options}
                        options = ", ".join(f"{k}={v}" for k, v in diff_options.items())
                        new_pid_info["options(diff)"] = options
                    new_rrev_info[new_pid] = new_pid_info
                new_ref_info[new_rrev] = new_rrev_info
            new_remote_info[ref] = new_ref_info
        new_info[remote] = new_remote_info

    print_serial(new_info)


def print_list_json(data):
    results = data["results"]
    myjson = json.dumps(results, indent=4)
    cli_out_write(myjson)


@conan_command(group="Consumer", formatters={"text": print_list_text,
                                             "json": print_list_json,
                                             "html": list_packages_html,
                                             "compact": print_list_compact})
def list(conan_api: ConanAPI, parser, *args):
    """
    List existing recipes, revisions, or packages in the cache (by default) or the remotes.
    """
    parser.add_argument('pattern', nargs="?",
                        help="A pattern in the form 'pkg/version#revision:package_id#revision', "
                             "e.g: zlib/1.2.13:* means all binaries for zlib/1.2.13. "
                             "If revision is not specified, it is assumed latest one.")
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="List only the packages matching a specific query, e.g, os=Windows AND "
                             "(arch=x86 OR compiler=gcc)")
    parser.add_argument("-r", "--remote", default=None, action="append",
                        help="Remote names. Accepts wildcards ('*' means all the remotes available)")
    parser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")
    parser.add_argument("-g", "--graph", help="Graph json file")
    parser.add_argument("-gb", "--graph-binaries", help="Which binaries are listed", action="append")
    parser.add_argument("-gr", "--graph-recipes", help="Which recipes are listed", action="append")
    parser.add_argument('--lru', default=None, action=OnceArgument,
                        help="List recipes and binaries that have not been recently used. Use a"
                             " time limit like --lru=5d (days) or --lru=4w (weeks),"
                             " h (hours), m(minutes)")

    args = parser.parse_args(*args)

    if args.pattern is None and args.graph is None:
        raise ConanException("Missing pattern or graph json file")
    if args.pattern and args.graph:
        raise ConanException("Cannot define both the pattern and the graph json file")
    if args.graph and args.lru:
        raise ConanException("Cannot define lru when loading a graph json file")
    if (args.graph_recipes or args.graph_binaries) and not args.graph:
        raise ConanException("--graph-recipes and --graph-binaries require a --graph input")
    if args.remote and args.lru:
        raise ConanException("'--lru' cannot be used in remotes, only in cache")

    if args.graph:
        graphfile = make_abs_path(args.graph)
        pkglist = MultiPackagesList.load_graph(graphfile, args.graph_recipes, args.graph_binaries)
    else:
        ref_pattern = ListPattern(args.pattern, rrev=None, prev=None)
        # If neither remote nor cache are defined, show results only from cache
        pkglist = MultiPackagesList()
        if args.cache or not args.remote:
            try:
                cache_list = conan_api.list.select(ref_pattern, args.package_query, remote=None,
                                                   lru=args.lru)
            except Exception as e:
                pkglist.add_error("Local Cache", str(e))
            else:
                pkglist.add("Local Cache", cache_list)
        if args.remote:
            remotes = conan_api.remotes.list(args.remote)
            for remote in remotes:
                try:
                    remote_list = conan_api.list.select(ref_pattern, args.package_query, remote)
                except Exception as e:
                    pkglist.add_error(remote.name, str(e))
                else:
                    pkglist.add(remote.name, remote_list)

    return {
        "results": pkglist.serialize(),
        "conan_api": conan_api,
        "cli_args": " ".join([f"{arg}={getattr(args, arg)}" for arg in vars(args) if getattr(args, arg)])
    }
