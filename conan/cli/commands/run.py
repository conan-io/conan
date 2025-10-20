import os

from conan.api.output import ConanOutput, LEVEL_WARNING, LEVEL_VERBOSE, LEVEL_STATUS, Color
from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command
from conan.cli.commands.install import run_install_command
from conan.internal.util.files import rmdir


@conan_command(group="Consumer")
def run(conan_api, parser, *args):
    """
    Run a command given a set of requirements from a recipe or from command line.
    """
    common_graph_args(parser)
    parser.add_argument("command", help="Command to run", nargs='+')
    parser.add_argument("--context", help="Context to use, host or build",
                        choices=["host", "build"], default="build")
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided path is a build-require')
    args = parser.parse_args(*args)
    validate_common_graph_args(args)
    command = " ".join(args.command)
    cwd = os.getcwd()

    # Default values for install
    setattr(args, "output_folder", ".conanrun")
    setattr(args, "generator", [])

    # TODO: Consider having --no-remote by default for run, and forcing the users use
    #  --remote if they want to access remotes, which would differ from conan install behaviour
    #  but might save time for some common use cases

    ConanOutput().info("Installing and building dependencies, this might take a while...",
                       fg=Color.BRIGHT_MAGENTA)
    previous_log_level = ConanOutput._conan_output_level
    if previous_log_level == LEVEL_STATUS:
        ConanOutput._conan_output_level = LEVEL_WARNING
    deps_graph, lockfile = run_install_command(conan_api, args, cwd)
    ConanOutput._conan_output_level = previous_log_level

    scope = "run" if args.context == "host" else "build"
    try:
        deps_graph.root.conanfile.run(command, cwd=cwd, scope=scope)
    except:
        raise
    finally:
        # Remove previous output folder to ensure a clean install
        if os.path.exists(args.output_folder):
            rmdir(args.output_folder)
