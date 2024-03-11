import json
import os

from conan.api.model import ListPattern
from conan.api.output import ConanOutput, cli_out_write, Color
from conan.cli import make_abs_path
from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands.list import prepare_pkglist_compact, print_serial
from conan.cli.formatters.graph import format_graph_html, format_graph_json, format_graph_dot
from conan.cli.formatters.graph.graph_info_text import format_graph_info
from conan.cli.printers.graph import print_graph_packages, print_graph_basic
from conan.errors import ConanException
from conan.internal.deploy import do_deploys
from conans.client.graph.graph import BINARY_MISSING
from conans.client.graph.install_graph import InstallGraph
from conans.model.recipe_ref import ref_matches, RecipeReference
from conans.model.version_range import VersionRange


def explain_formatter_text(data):
    if "closest_binaries" in data:
        # To be able to reuse the print_list_compact method,
        # we need to wrap this in a MultiPackagesList
        pkglist = data["closest_binaries"]
        prepare_pkglist_compact(pkglist)
        print_serial(pkglist)


def explain_formatter_json(data):
    myjson = json.dumps(data, indent=4)
    cli_out_write(myjson)


@conan_command(group="Consumer")
def graph(conan_api, parser, *args):
    """
    Compute a dependency graph, without installing or building the binaries.
    """


def cli_build_order(build_order):
    # TODO: Very simple cli output, probably needs to be improved
    build_order = build_order["order"] if isinstance(build_order, dict) else build_order
    for level in build_order:
        for item in level:
            # If this is a configuration order, it has no packages entry, each item is a package
            if 'packages' in item:
                for package_level in item['packages']:
                    for package in package_level:
                        cli_out_write(f"{item['ref']}:{package['package_id']} - {package['binary']}")
            else:
                cli_out_write(f"{item['ref']}:{item['package_id']} - {item['binary']}")


def json_build_order(build_order):
    cli_out_write(json.dumps(build_order, indent=4))


@conan_subcommand(formatters={"text": cli_build_order, "json": json_build_order})
def graph_build_order(conan_api, parser, subparser, *args):
    """
    Compute the build order of a dependency graph.
    """
    common_graph_args(subparser)
    subparser.add_argument("--order-by", choices=['recipe', 'configuration'],
                           help='Select how to order the output, "recipe" by default if not set.')
    subparser.add_argument("--reduce", action='store_true', default=False,
                           help='Reduce the build order, output only those to build. Use this '
                                'only if the result will not be merged later with other build-order')
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")
    if args.order_by is None:
        ConanOutput().warning("Please specify --order-by argument", warn_tag="deprecated")

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial,
                                               overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    if path:
        deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                         args.user, args.channel,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.build, args.update)
    else:
        deps_graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.build, args.update)
    print_graph_basic(deps_graph)
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    out = ConanOutput()
    out.title("Computing the build order")

    install_graph = InstallGraph(deps_graph, order_by=args.order_by)
    if args.reduce:
        if args.order_by is None:
            raise ConanException("--reduce needs --order-by argument defined")
        install_graph.reduce()
    install_order_serialized = install_graph.install_build_order()
    if args.order_by is None:  # legacy
        install_order_serialized = install_order_serialized["order"]

    lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)

    return install_order_serialized


@conan_subcommand(formatters={"text": cli_build_order, "json": json_build_order})
def graph_build_order_merge(conan_api, parser, subparser, *args):
    """
    Merge more than 1 build-order file.
    """
    subparser.add_argument("--file", nargs="?", action="append", help="Files to be merged")
    subparser.add_argument("--reduce", action='store_true', default=False,
                           help='Reduce the build order, output only those to build. Use this '
                                'only if the result will not be merged later with other build-order')
    args = parser.parse_args(*args)
    if not args.file or len(args.file) < 2:
        raise ConanException("At least 2 files are needed to be merged")

    result = InstallGraph.load(make_abs_path(args.file[0]))
    if result.reduced:
        raise ConanException(f"Reduced build-order file cannot be merged: {args.file[0]}")
    for f in args.file[1:]:
        install_graph = InstallGraph.load(make_abs_path(f))
        if install_graph.reduced:
            raise ConanException(f"Reduced build-order file cannot be merged: {f}")
        result.merge(install_graph)

    if args.reduce:
        result.reduce()
    install_order_serialized = result.install_build_order()
    if getattr(result, "legacy"):
        install_order_serialized = install_order_serialized["order"]
    return install_order_serialized


@conan_subcommand(formatters={"text": format_graph_info,
                              "html": format_graph_html,
                              "json": format_graph_json,
                              "dot": format_graph_dot})
def graph_info(conan_api, parser, subparser, *args):
    """
    Compute the dependency graph and show information about it.
    """
    common_graph_args(subparser)
    subparser.add_argument("--check-updates", default=False, action="store_true",
                           help="Check if there are recipe updates")
    subparser.add_argument("--filter", action="append",
                           help="Show only the specified fields")
    subparser.add_argument("--package-filter", action="append",
                           help='Print information only for packages that match the patterns')
    subparser.add_argument("-d", "--deployer", action="append",
                           help='Deploy using the provided deployer to the output folder')
    subparser.add_argument("-df", "--deployer-folder",
                           help="Deployer output folder, base build folder by default if not set")
    subparser.add_argument("--build-require", action='store_true', default=False,
                           help='Whether the provided reference is a build-require')
    args = parser.parse_args(*args)

    # parameter validation
    validate_common_graph_args(args)
    if args.format in ("html", "dot") and args.filter:
        raise ConanException(f"Formatted output '{args.format}' cannot filter fields")

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial,
                                               overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    if path:
        deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                         args.user, args.channel,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         check_updates=args.check_updates,
                                                         is_build_require=args.build_require)
    else:
        deps_graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         check_updates=args.check_updates)
    print_graph_basic(deps_graph)
    if deps_graph.error:
        ConanOutput().info("Graph error", Color.BRIGHT_RED)
        ConanOutput().info("    {}".format(deps_graph.error), Color.BRIGHT_RED)
    else:
        conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                         lockfile=lockfile)
        print_graph_packages(deps_graph)

        conan_api.install.install_system_requires(deps_graph, only_info=True)
        conan_api.install.install_sources(deps_graph, remotes=remotes)

        lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                      clean=args.lockfile_clean)
        conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
        if args.deployer:
            base_folder = args.deployer_folder or os.getcwd()
            do_deploys(conan_api, deps_graph, args.deployer, None, base_folder)

    return {"graph": deps_graph,
            "field_filter": args.filter,
            "package_filter": args.package_filter,
            "conan_api": conan_api}


@conan_subcommand(formatters={"text": explain_formatter_text,
                              "json": explain_formatter_json})
def graph_explain(conan_api, parser,  subparser, *args):
    """
    Explain what is wrong with the dependency graph, like report missing binaries closest
    alternatives, trying to explain why the existing binaries do not match
    """
    common_graph_args(subparser)
    subparser.add_argument("--check-updates", default=False, action="store_true",
                           help="Check if there are recipe updates")
    subparser.add_argument("--build-require", action='store_true', default=False,
                           help='Whether the provided reference is a build-require')
    subparser.add_argument('--missing', nargs="?",
                           help="A pattern in the form 'pkg/version#revision:package_id#revision', "
                                "e.g: zlib/1.2.13:* means all binaries for zlib/1.2.13. "
                                "If revision is not specified, it is assumed latest one.")

    args = parser.parse_args(*args)
    # parameter validation
    validate_common_graph_args(args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial,
                                               overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    if path:
        deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                         args.user, args.channel,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         check_updates=args.check_updates,
                                                         is_build_require=args.build_require)
    else:
        deps_graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         check_updates=args.check_updates)
    print_graph_basic(deps_graph)
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    ConanOutput().title("Retrieving and computing closest binaries")
    # compute ref and conaninfo
    missing = args.missing
    for node in deps_graph.ordered_iterate():
        if ((not missing and node.binary == BINARY_MISSING)   # First missing binary or
                or (missing and ref_matches(node.ref, missing, is_consumer=None))):  # specified one
            ref = node.ref
            conaninfo = node.conanfile.info
            break
    else:
        raise ConanException("There is no missing binary")

    pkglist = conan_api.list.explain_missing_binaries(ref, conaninfo, remotes)

    ConanOutput().title("Closest binaries")
    return {"closest_binaries": pkglist.serialize()}


def outdated_text_formatter(result):
    cli_out_write("======== Outdated dependencies ========", fg=Color.BRIGHT_MAGENTA)

    for value in result.values():
        cli_out_write(value["current"].name, fg=Color.BRIGHT_YELLOW)
        cli_out_write(f'\tCurrent: {value["current"].repr_humantime()}', fg=Color.BRIGHT_CYAN)
        cli_out_write(f'\tLatest in range:  {value["latest_range"].repr_humantime()}',
                      fg=Color.BRIGHT_CYAN)
        cli_out_write(
            f'\tLatest in remote(s):  {value["latest_remote"]["ref"].repr_humantime()} - {value["latest_remote"]["remote"].name}',
            fg=Color.BRIGHT_CYAN)


def outdated_json_formatter(result):
    output = {key: {"current": value["current"].repr_humantime(),
                    "latest_range": value["latest_range"].repr_humantime(),
                    "latest_remote": {"ref": value["latest_remote"]["ref"].repr_humantime(),
                                      "remote": str(value["latest_remote"]["remote"])}}
              for key, value in result.items()}
    cli_out_write(json.dumps(output))


@conan_subcommand(formatters={"text": outdated_text_formatter, "json": outdated_json_formatter})
def graph_outdated(conan_api, parser, subparser, *args):
    """
    List the dependencies in the graph and it's newer versions in the remote
    """
    common_graph_args(subparser)
    subparser.add_argument("--check-updates", default=False, action="store_true",
                           help="Check if there are recipe updates")
    subparser.add_argument("--build-require", action='store_true', default=False,
                           help='Whether the provided reference is a build-require')
    args = parser.parse_args(*args)
    # parameter validation
    validate_common_graph_args(args)
    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial,
                                               overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    if path:
        deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                         args.user, args.channel,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         check_updates=args.check_updates,
                                                         is_build_require=args.build_require)
    else:
        deps_graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         check_updates=args.check_updates)
    print_graph_basic(deps_graph)

    dependencies = deps_graph.nodes[1:]
    resolved_ranges = list(deps_graph.resolved_ranges.keys())

    latest_recipe = []

    ConanOutput().title("Checking remotes")

    # Data structure for solve the repeated dependencies in graph
    dict_nodes = {}
    for node in dependencies:
        if node.name in dict_nodes:
            dict_nodes[node.name].append(node)
        else:
            dict_nodes[node.name] = [node]
    print("--")
    for node_name, node_list in dict_nodes.items():
        ref_pattern = ListPattern(node_name, rrev=None, prev=None)
        latest_remote_ref, found_remote = None, None
        for remote in remotes:
            try:
                remote_ref_list = conan_api.list.select(ref_pattern, package_query=None,
                                                        remote=remote)
                if not remote_ref_list.recipes:
                    continue
            except Exception:
                ConanOutput(f"{node_name} not found in remote {remote.name}")
                continue
            str_latest_ref = list(remote_ref_list.recipes.keys())[-1]
            recipe_ref = RecipeReference.loads(f"{str_latest_ref}")
            if latest_remote_ref is None or latest_remote_ref < recipe_ref: # TODO: check local librarie doesn't have newer version
                latest_remote_ref = recipe_ref
                found_remote = remote
        latest_node = max(node_list, key=lambda x: x.ref)
        latest_recipe.append((latest_node, node_list,  latest_remote_ref, found_remote))

    return {node.name: {"current": node.ref,
                        "current_vesions": node_list,
                        "latest_range": latest_in_range_ref,
                        "latest_remote": {"ref": "latest_remote_ref",
                                          "remote": found_remote},
                        "resolved_ranges": [r for r in resolved_ranges if r.name == node.name]}
            for node, node_list, found_remote, latest_in_range_ref in latest_recipe}
