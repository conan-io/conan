import os

from conan.api.output import ConanOutput
from conan.cli.command import conan_command
from conan.cli import make_abs_path
from conan.cli.args import add_lockfile_args, add_common_install_arguments, add_reference_args
from conan.cli.printers import print_profiles
from conan.cli.printers.graph import print_graph_packages, print_graph_basic


@conan_command(group='Creator')
def build(conan_api, parser, *args):
    """
    Install dependencies and call the build() method.
    """
    parser.add_argument("path", nargs="?",
                        help='Path to a python-based recipe file or a folder '
                             'containing a conanfile.py recipe. conanfile.txt '
                             'cannot be used with conan build.')
    add_reference_args(parser)
    # TODO: Missing --build-require argument and management
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    add_common_install_arguments(parser)
    add_lockfile_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    folder = os.path.dirname(path)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []

    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)
    print_profiles(profile_host, profile_build)

    deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                     args.user, args.channel,
                                                     profile_host, profile_build, lockfile, remotes,
                                                     args.update)
    print_graph_basic(deps_graph)
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    out = ConanOutput()
    out.title("Installing packages")
    conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)

    source_folder = folder
    output_folder = make_abs_path(args.output_folder, cwd) if args.output_folder else None
    out.title("Finalizing install (deploy, generators)")
    conan_api.install.install_consumer(deps_graph=deps_graph, source_folder=source_folder,
                                       output_folder=output_folder)

    out.title("Calling build()")
    conanfile = deps_graph.root.conanfile
    conan_api.local.build(conanfile)

    lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, source_folder)
    return deps_graph
