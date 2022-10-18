import json
import os

from conan.api.output import ConanOutput, cli_out_write
from conan.api.subapi.install import do_deploys
from conan.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand, \
    Extender
from conan.cli.commands import make_abs_path
from conan.cli.commands.install import graph_compute, common_graph_args
from conan.cli.common import save_lockfile_out
from conan.cli.formatters.graph import format_graph_html, format_graph_json, format_graph_dot
from conan.cli.formatters.graph.graph_info_text import format_graph_info
from conans.client.graph.install_graph import InstallGraph
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['consumer'])
def graph(conan_api, parser, *args):
    """
    Computes a dependency graph, without  installing or building the binaries
    """


def cli_build_order(build_order):
    # TODO: Very simple cli output, probably needs to be improved
    for level in build_order:
        for item in level:
            for package_level in item['packages']:
                for package in package_level:
                    cli_out_write(f"{item['ref']}:{package['package_id']} - {package['binary']}")


def json_build_order(build_order):
    cli_out_write(json.dumps(build_order, indent=4))


@conan_subcommand(formatters={"text": cli_build_order, "json": json_build_order})
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

    deps_graph, lockfile = graph_compute(args, conan_api, partial=args.lockfile_partial)

    out = ConanOutput()
    out.title("Computing the build order")
    install_graph = InstallGraph(deps_graph)
    install_order_serialized = install_graph.install_build_order()
    return install_order_serialized


@conan_subcommand(formatters={"text": cli_build_order, "json": json_build_order})
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
    return install_order_serialized


@conan_subcommand(formatters={"text": format_graph_info,
                              "html": format_graph_html,
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
    subparser.add_argument("--deploy", action=Extender,
                           help='Deploy using the provided deployer to the output folder')
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")

    if args.format is not None and (args.filter or args.package_filter):
        raise ConanException("Formatted outputs cannot be filtered")

    deps_graph, lockfile = graph_compute(args, conan_api, partial=args.lockfile_partial,
                                         allow_error=True)

    save_lockfile_out(args, deps_graph, lockfile, os.getcwd())
    if args.deploy:
        base_folder = os.getcwd()
        do_deploys(conan_api, deps_graph, args.deploy, base_folder)

    return {"graph": deps_graph,
            "field_filter": args.filter,
            "package_filter": args.package_filter}
