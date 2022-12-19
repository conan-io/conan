import json
import os

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.printers.graph import print_graph_packages
from conan.internal.deploy import do_deploys
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands import make_abs_path
from conan.cli.args import common_graph_args
from conan.cli.formatters.graph import format_graph_html, format_graph_json, format_graph_dot
from conan.cli.formatters.graph.graph_info_text import format_graph_info
from conans.client.graph.install_graph import InstallGraph
from conans.errors import ConanException


@conan_command(group="Consumer")
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

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
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
    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    out = ConanOutput()
    out.title("Computing the build order")
    install_graph = InstallGraph(deps_graph)
    install_order_serialized = install_graph.install_build_order()

    lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)
    conanfile_path = os.path.dirname(deps_graph.root.path) if deps_graph.root.path else os.getcwd()
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, conanfile_path)

    return install_order_serialized


@conan_subcommand(formatters={"text": cli_build_order, "json": json_build_order})
def graph_build_order_merge(conan_api, parser, subparser, *args):
    """
    Merges more than 1 build-order file
    """
    subparser.add_argument("--file", nargs="?", action="append", help="Files to be merged")
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
    subparser.add_argument("--filter", action="append",
                           help="Show only the specified fields")
    subparser.add_argument("--package-filter", action="append",
                           help='Print information only for packages that match the patterns')
    subparser.add_argument("--deploy", action="append",
                           help='Deploy using the provided deployer to the output folder')
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")
    if not args.path and not args.requires and not args.tool_requires:
        raise ConanException("Please specify at least a path to a conanfile or a valid reference.")
    if args.format is not None and (args.filter or args.package_filter):
        raise ConanException("Formatted outputs cannot be filtered")

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    if path:
        deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                         args.user, args.channel,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         allow_error=True,
                                                         check_updates=args.check_updates)
    else:
        deps_graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         allow_error=True,
                                                         check_updates=args.check_updates)
    if not deps_graph.error:
        conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                         lockfile=lockfile)
        print_graph_packages(deps_graph)

        lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                      clean=args.lockfile_clean)
        conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, os.getcwd())
        if args.deploy:
            base_folder = os.getcwd()
            do_deploys(conan_api, deps_graph, args.deploy, base_folder)

    return {"graph": deps_graph,
            "field_filter": args.filter,
            "package_filter": args.package_filter,
            "conan_api": conan_api}
