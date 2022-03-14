import json
import os

from conans.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand, \
    Extender
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import graph_compute, common_graph_args
from conans.cli.formatters.graph import format_graph_html, format_graph_json, format_graph_dot, \
    print_graph_info
from conans.cli.output import ConanOutput
from conans.client.graph.install_graph import InstallGraph
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['consumer'])
def graph(conan_api, parser, *args):
    """
    Computes a dependency graph, without  installing or building the binaries
    """


def cli_build_order(build_order):
    # TODO: Very simple cli output, probably needs to be improved
    output = ConanOutput()
    for level in build_order:
        for item in level:
            output.writeln(item["ref"])


def json_build_order(build_order):
    return json.dumps(build_order, indent=4)


@conan_subcommand(formatters={"json": json_build_order})
def graph_build_order(conan_api, parser, subparser, *args):
    """
    Computes the build order of a dependency graph
    """
    common_graph_args(subparser)
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")

    deps_graph, lockfile = graph_compute(args, conan_api, strict=args.lockfile_strict)

    out = ConanOutput()
    out.highlight("-------- Computing the build order ----------")
    install_graph = InstallGraph(deps_graph)
    install_order_serialized = install_graph.install_build_order()
    cli_build_order(install_order_serialized)
    return install_order_serialized


@conan_subcommand(formatters={"json": json_build_order})
def graph_build_order_merge(conan_api, parser, subparser, *args):
    """
    Merges more than 1 build-order file
    """
    subparser.add_argument("--file", nargs="?", action=Extender, help="Files to be merged")
    args = parser.parse_args(*args)

    result = InstallGraph()
    for f in args.file:
        f = make_abs_path(f)
        install_graph = InstallGraph.load(f)
        result.merge(install_graph)

    install_order_serialized = result.install_build_order()
    cli_build_order(install_order_serialized)
    return install_order_serialized


@conan_subcommand(formatters={"html": format_graph_html,
                              "json": format_graph_json,
                              "dot": format_graph_dot})
def graph_info(conan_api, parser, subparser, *args):
    """
    Computes the dependency graph and shows information about it
    """
    common_graph_args(subparser)
    subparser.add_argument("--check-updates", default=False, action="store_true")
    subparser.add_argument("--filter", nargs=1, action=Extender,
                           help="Show only the specified fields")
    subparser.add_argument("--package-filter", nargs=1, action=Extender,
                           help='Print information only for packages that match the patterns')
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")

    if args.format is not None and (args.filter or args.package_filter):
        raise ConanException("Formatted outputs cannot be filtered")

    deps_graph, lockfile = graph_compute(args, conan_api, strict=args.lockfile_strict)
    if not args.format:
        print_graph_info(deps_graph, args.filter, args.package_filter)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, os.getcwd())
        ConanOutput().info(f"Saving lockfile: {lockfile_out}")
        lockfile.save(lockfile_out)

    return deps_graph, os.path.join(conan_api.cache_folder, "templates")

