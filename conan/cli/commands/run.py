import os
import tempfile

from conan.api.output import ConanOutput, LEVEL_WARNING, LEVEL_STATUS, Color
from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command
from conan.cli.commands.install import run_install_command


@conan_command(group="Consumer")
def run(conan_api, parser, *args):
    """
    (Experimental) Run a command given a set of requirements from a recipe or from command line.
    """
    common_graph_args(parser)
    parser.add_argument("command", help="Command to run", nargs='+')
    parser.add_argument("--context", help="Context to use, by default both contexts are activated "
                                          "if not specified",
                        choices=["host", "build"], default=None)
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided path is a build-require')
    args = parser.parse_args(*args)
    validate_common_graph_args(args)
    command = " ".join(args.command)
    cwd = os.getcwd()

    ConanOutput().info("Installing and building dependencies, this might take a while...",
                       fg=Color.BRIGHT_MAGENTA, newline=False)
    previous_log_level = ConanOutput._conan_output_level
    if previous_log_level == LEVEL_STATUS:
        ConanOutput._conan_output_level = LEVEL_WARNING

    with tempfile.TemporaryDirectory("conanrun") as tmpdir:
        # Default values for install
        setattr(args, "output_folder", tmpdir)
        setattr(args, "generator", [])
        time.sleep(1)
        deps_graph, lockfile = run_install_command(conan_api, args, cwd)

        ConanOutput().clear_line()
        context_env_map = {
            "host": "conanrun",
            "build": "conanbuild"
        }
        envfiles = ["conanbuild", "conanrun"] if args.context is None \
            else [context_env_map.get(args.context)]
        deps_graph.root.conanfile.run(command, cwd=cwd, env=envfiles)
