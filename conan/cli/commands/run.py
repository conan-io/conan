import os

from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command
from conan.cli.commands.install import run_install_command


@conan_command(group="Consumer")
def run(conan_api, parser, *args):
    """
    Run a command in the environment defined by a previous call to 'conan install'.
    """
    common_graph_args(parser)
    parser.add_argument("command", help="Command to run",
                        nargs='+')
    parser.add_argument("--context", help="Context to use, host or build",
                        choices=["host", "build"], default="host")
    # Install commands
    parser.add_argument("-g", "--generator", action="append", help='Generators to use')
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided path is a build-require')
    args = parser.parse_args(*args)
    validate_common_graph_args(args)
    command = " ".join(args.command)
    cwd = os.getcwd()

    deps_graph, lockfile = run_install_command(conan_api, args, cwd)

    # TODO:
    # - Context: could be both host and build?
    # - Output folder? /tmp, $CWD/.conanrun, ~/.conan
    # - Conan internal loader: is it good idea to initialize conan_helpers in a virtual node?
    # - Tests
    scope = "run" if args.context == "host" else "build"
    deps_graph.root.conanfile.run(command, cwd=cwd, scope=scope)
