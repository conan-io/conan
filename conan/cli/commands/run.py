import os
import platform
import tempfile

from conan.api.output import ConanOutput, LEVEL_STATUS, Color, LEVEL_ERROR, LEVEL_QUIET
from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command
from conan.cli.commands.install import _run_install_command
from conan.errors import ConanException
from conan.internal.util.files import save


@conan_command(group="Consumer")
def run(conan_api, parser, *args):
    """
    (Experimental) Run a command given a set of requirements from a recipe or from command line.
    """
    common_graph_args(parser)
    parser.add_argument("command", help="Command to run")
    parser.add_argument("--context", help="Context to use, by default both contexts are activated "
                                          "if not specified",
                        choices=["host", "build"], default=None)
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided path is a build-require')
    args = parser.parse_args(*args)
    validate_common_graph_args(args)
    cwd = os.getcwd()

    ConanOutput().info("Installing and building dependencies, this might take a while...",
                       fg=Color.BRIGHT_MAGENTA)
    previous_log_level = ConanOutput.get_output_level()
    if previous_log_level == LEVEL_STATUS:
        ConanOutput.set_output_level(LEVEL_QUIET)

    with tempfile.TemporaryDirectory("conanrun") as tmpdir:
        # Default values for install
        setattr(args, "output_folder", tmpdir)
        setattr(args, "generator", [])
        # If there is no conanfile in the cwd and no --requires/--tool-requires,
        # use an in-memory virtual conanfile so that a profile [tool_requires]
        # section is enough and executables from them can be executed
        if args.path == "." and not args.requires and not args.tool_requires \
                and not os.path.isfile(os.path.join(cwd, "conanfile.py")) \
                and not os.path.isfile(os.path.join(cwd, "conanfile.txt")):
            args.path = None
            args.tool_requires = []
        try:
            deps_graph, lockfile, _ = _run_install_command(conan_api, args, cwd,
                                                           return_install_error=False)
        except ConanException as e:
            ConanOutput.set_output_level(previous_log_level)
            ConanOutput().error("Error installing the dependencies. To debug this, you can either:\n"
                                " - Re-run the command with increased verbosity (-v, -vv)\n"
                                " - Run 'conan install' first to ensure dependencies are installed, "
                                "or to see errors during installation\n")
            raise e

        context_env_map = {
            "build": "conanbuild",
            "host": "conanrun",
        }
        envfiles = list(context_env_map.values()) if args.context is None \
            else [context_env_map.get(args.context)]
        # Defer command parsing until after env activation runs, so that
        # $VAR/%VAR% references in the user command are expanded using the
        # activated environment (buildenv/runenv from deps).
        if platform.system() == "Windows":
            script = os.path.join(tmpdir, "conanrun_cmd.bat")
            save(script, f"@echo off\n{args.command}\n")
            command = f'call "{script}"'
        else:
            script = os.path.join(tmpdir, "conanrun_cmd.sh")
            save(script, f"{args.command}\n")
            command = f'"{script}"'
        ConanOutput.set_output_level(LEVEL_ERROR)
        deps_graph.root.conanfile.run(command, cwd=cwd, env=envfiles)
