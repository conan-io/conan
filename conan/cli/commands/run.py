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

    # This would need to be cleaned up a lot
    parser.add_argument("-g", "--generator", action="append", help='Generators to use')
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    parser.add_argument("-d", "--deployer", action="append",
                        help="Deploy using the provided deployer to the output folder. "
                             "Built-in deployers: 'full_deploy', 'direct_deploy', 'runtime_deploy'")
    parser.add_argument("--deployer-folder",
                        help="Deployer output folder, base build folder by default if not set")
    parser.add_argument("--deployer-package", action="append",
                        help="Execute the deploy() method of the packages matching "
                             "the provided patterns")
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided path is a build-require')
    parser.add_argument("--envs-generation", default=None, choices=["false"],
                        help="Generation strategy for virtual environment files for the root")
    args = parser.parse_args(*args)
    validate_common_graph_args(args)
    command = " ".join(args.command)
    cwd = os.getcwd()

    deps_graph, lockfile = run_install_command(conan_api, args, cwd)

    # TODO: most of this will need to go into something like
    #conan_api.local.run(args.command, cwd, ...)
    import subprocess

    # TODO: We'll also need a way to find the env files,
    # harcoded for now, but things to take into account are:
    # - tools.env.virtualenv:powershell conf when using Windows
    #    - then different shells/prefixes will be necessary
    # - what context? How do we choose it? Is the current parameter a good idea?
    # - error handling
    # - Should we capture the output? Does not look like a good idea for interactive commands

    generators_folder = deps_graph.root.conanfile.folders.generators_folder
    prefix = "conanbuild.sh" if args.context == "build" else "conanrun.sh"
    composed_command = f". {os.path.join(generators_folder, prefix)} && {command}"
    subprocess.run(composed_command, shell=True, cwd=cwd, check=True)
