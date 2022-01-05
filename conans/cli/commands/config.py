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
from conans.model.conf import DEFAULT_CONFIGURATION


@conan_command(group=COMMAND_GROUPS['consumer'])
def config(conan_api, parser, *args):
    """
    Computes a dependency graph, without  installing or building the binaries
    """


def json_build_order(build_order):
    return json.dumps(build_order, indent=4)


@conan_subcommand(formatters={"json": json_build_order})
def config_install(conan_api, parser, subparser, *args):
    """
    Computes the build order of a dependency graph
    """
    common_graph_args(subparser)
    args = parser.parse_args(*args)

    return install_order_serialized


@conan_subcommand(formatters={"json": json_build_order})
def config_list(conan_api, parser, subparser, *args):
    """
    return available built-in [conf] configuration items
    """
    out = ConanOutput()
    out.info("Supported Conan *experimental* global.conf and [conf] properties:")
    for key, value in DEFAULT_CONFIGURATION.items():
        out.info("{}: {}".format(key, value))

    return DEFAULT_CONFIGURATION


@conan_subcommand(formatters={"text": lambda x: x})
def config_home(conan_api, parser, subparser, *args):
    """
    Gets the Conan home folder
    """
    home = conan_api.config.home()
    ConanOutput().info(f"Current Conan home: {home}")
    return home


@conan_subcommand()
def config_init(conan_api, parser, subparser, *args):
    """
    Initialize Conan home configuration: settings, conf and remotes
    """
    subparser.add_argument("-f", "--force", action='store_true',
                           help="Force the removal of config if exists")
    args = parser.parse_args(*args)
    home = conan_api.config.init(force=args.force)
    return home
