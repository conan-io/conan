import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import graph_compute, _get_conanfile_path
from conans.cli.common import _add_common_install_arguments, _help_build_policies, \
    get_multiple_remotes
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.conanfile.build import run_build_method
from conans.util.files import mkdir, chdir


@conan_command(group=COMMAND_GROUPS['creator'])
def build(conan_api, parser, *args):
    """
    Install + calls the build() method
    """
    parser.add_argument("path", nargs="?",
                        help="Path to a folder containing a recipe (conanfile.py "
                             "or conanfile.txt) or to a recipe file. e.g., "
                             "./my_project/conanfile.txt.")
    parser.add_argument("--name", action=OnceArgument,
                        help='Provide a package name if not specified in conanfile')
    parser.add_argument("--version", action=OnceArgument,
                        help='Provide a package version if not specified in conanfile')
    parser.add_argument("--user", action=OnceArgument,
                        help='Provide a user')
    parser.add_argument("--channel", action=OnceArgument,
                        help='Provide a channel')
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    parser.add_argument("-sf", "--source-folder", help='The root source folder')
    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = _get_conanfile_path(args.path, cwd, py=True)
    remote = get_multiple_remotes(conan_api, args.remote)

    deps_graph, lockfile = graph_compute(args, conan_api)

    out = ConanOutput()
    out.highlight("\n-------- Installing packages ----------")
    conan_api.install.install_binaries(deps_graph=deps_graph, build_modes=args.build,
                                       remotes=remote, update=args.update)

    source_folder = make_abs_path(args.source_folder, cwd) if args.source_folder else cwd
    output_folder = make_abs_path(args.output_folder, cwd) if args.output_folder else cwd
    out.highlight("\n-------- Finalizing install (imports, deploy, generators) ----------")
    conan_api.install.install_consumer(deps_graph=deps_graph, source_folder=source_folder,
                                       output_folder=output_folder)

    # TODO: Decide API to put this
    app = ConanApp(conan_api.cache_folder)
    conanfile = deps_graph.root.conanfile
    mkdir(conanfile.build_folder)
    with chdir(conanfile.build_folder):
        run_build_method(conanfile, app.hook_manager, conanfile_path=path)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        out.info(f"Saving lockfile: {lockfile_out}")
        lockfile.save(lockfile_out)
