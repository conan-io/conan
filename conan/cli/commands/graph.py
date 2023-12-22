import json
import os

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
from conans.model.recipe_ref import ref_matches


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
    Compute the build order of a dependency graph.
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
    install_graph = InstallGraph(deps_graph)
    install_order_serialized = install_graph.install_build_order()

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
        if node.binary == BINARY_MISSING:
            if not missing or ref_matches(node.ref, missing, is_consumer=None):
                ref = node.ref
                conaninfo = node.conanfile.info
                break
    else:
        raise ConanException("There is no missing binary")

    pkglist = conan_api.list.explain_missing_binaries(ref, conaninfo, remotes)

    ConanOutput().title("Closest binaries")
    return {
        "closest_binaries": pkglist.serialize(),
    }
