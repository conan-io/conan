import json

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument, conan_subcommand, \
    Extender
from conans.cli.commands.install import graph_compute
from conans.cli.common import _add_common_install_arguments, _help_build_policies
from conans.cli.output import ConanOutput
from conans.client.conan_api import _make_abs_path
from conans.client.graph.install_graph import InstallGraph
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['consumer'])
def graph(conan_api, parser, *args):
    """
    Computes a dependency graph, without  installing or building the binaries
    """


def text_build_order(build_order):
    result = []
    for level in build_order:
        for item in level:
            result.append(item["ref"])
    return "\n".join(result)


def cli_build_order(build_order):
    output = ConanOutput()
    for level in build_order:
        for item in level:
            output.writeln(item["ref"])


def json_build_order(build_order):
    return json.dumps(build_order, indent=4)


@conan_subcommand(formatters={"txt": text_build_order, "json": json_build_order})
def graph_build_order(conan_api, parser, subparser, *args):
    """
    Computes the build order of a dependency graph
    """
    subparser.add_argument("path", nargs="?",
                           help="Path to a folder containing a recipe (conanfile.py "
                                "or conanfile.txt) or to a recipe file. e.g., "
                                "./my_project/conanfile.txt.")
    subparser.add_argument("--name", action=OnceArgument,
                           help='Provide a package name if not specified in conanfile')
    subparser.add_argument("--version", action=OnceArgument,
                           help='Provide a package version if not specified in conanfile')
    subparser.add_argument("--user", action=OnceArgument,
                           help='Provide a user')
    subparser.add_argument("--channel", action=OnceArgument,
                           help='Provide a channel')

    subparser.add_argument("--reference", action=OnceArgument,
                           help='Provide a package reference instead of a conanfile')

    _add_common_install_arguments(subparser, build_help=_help_build_policies.format("never"))
    subparser.add_argument("--build-require", action='store_true', default=False,
                           help='The provided reference is a build-require')
    parser.add_argument("--require-override", action="append",
                        help="Define a requirement override")

    args = parser.parse_args(*args)

    # parameter validation
    if args.reference and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--reference")

    deps_graph, lockfile = graph_compute(args, conan_api)

    out = ConanOutput()
    out.highlight("-------- Computing the build order ----------")
    install_graph = InstallGraph(deps_graph)
    install_order_serialized = install_graph.install_build_order()
    cli_build_order(install_order_serialized)
    return install_order_serialized


@conan_subcommand(formatters={"txt": text_build_order, "json": json_build_order})
def graph_build_order_merge(conan_api, parser, subparser, *args):
    """
    Merges more than 1 build-order file
    """

    subparser.add_argument("--file", nargs="?", action=Extender, help="Files to be merged")
    args = parser.parse_args(*args)

    result = InstallGraph()
    for f in args.file:
        f = _make_abs_path(f)
        install_graph = InstallGraph.load(f)
        result.merge(install_graph)

    install_order_serialized = result.install_build_order()
    cli_build_order(install_order_serialized)
    return install_order_serialized
