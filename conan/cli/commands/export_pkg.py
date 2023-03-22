import json
import os

from conan.api.output import cli_out_write, ConanOutput
from conan.cli.command import conan_command, OnceArgument
from conan.cli.args import add_lockfile_args, add_profiles_args, add_reference_args
from conan.cli import make_abs_path
from conan.cli.commands.create import _get_test_conanfile_path
from conan.cli.printers.graph import print_graph_basic


def json_export_pkg(info):
    deps_graph = info
    cli_out_write(json.dumps({"graph": deps_graph.serialize()}, indent=4))


@conan_command(group="Creator", formatters={"json": json_export_pkg})
def export_pkg(conan_api, parser, *args):
    """
    Create a package directly from pre-compiled binaries.
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided reference is a build-require')
    parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                        help='Alternative test folder name. By default it is "test_package". '
                             'Use "" to skip the test stage')
    parser.add_argument("-sb", "--skip-binaries", action="store_true",
                        help="Skip installing dependencies binaries")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')

    add_reference_args(parser)
    add_lockfile_args(parser)
    add_profiles_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    test_conanfile_path = _get_test_conanfile_path(args.test_folder, path)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, conanfile_path=path,
                                               cwd=cwd, partial=args.lockfile_partial)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []

    ref, conanfile = conan_api.export.export(path=path, name=args.name, version=args.version,
                                             user=args.user, channel=args.channel, lockfile=lockfile,
                                             remotes=remotes)
    # The package_type is not fully processed at export
    assert conanfile.package_type != "python-require", "A python-require cannot be export-pkg"
    lockfile = conan_api.lockfile.update_lockfile_export(lockfile, conanfile, ref,
                                                         args.build_require)

    # TODO: Maybe we want to be able to export-pkg it as --build-require
    deps_graph = conan_api.graph.load_graph_consumer(path,
                                                     ref.name, ref.version, ref.user, ref.channel,
                                                     profile_host=profile_host,
                                                     profile_build=profile_build,
                                                     lockfile=lockfile, remotes=remotes, update=None,
                                                     is_build_require=args.build_require)

    print_graph_basic(deps_graph)
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, build_mode=[ref.name], lockfile=lockfile,
                                     remotes=remotes)
    deps_graph.report_graph_error()

    root_node = deps_graph.root
    root_node.ref = ref

    if not args.skip_binaries:
        # unless the user explicitly opts-out with --skip-binaries, it is necessary to install
        # binaries, in case there are build_requires necessary to export, like tool-requires=cmake
        # and package() method doing ``cmake.install()``
        # for most cases, deps would be in local cache already because of a previous "conan install"
        # but if it is not the case, the binaries from remotes will be downloaded
        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)
    source_folder = os.path.dirname(path)
    output_folder = make_abs_path(args.output_folder, cwd) if args.output_folder else None
    conan_api.install.install_consumer(deps_graph=deps_graph, source_folder=source_folder,
                                       output_folder=output_folder)

    ConanOutput().title("Exporting recipe and package to the cache")
    conan_api.export.export_pkg(deps_graph, source_folder, output_folder)

    lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)

    if test_conanfile_path:
        from conan.cli.commands.test import run_test
        deps_graph = run_test(conan_api, test_conanfile_path, ref, profile_host, profile_build,
                              remotes=None, lockfile=lockfile, update=False, build_modes=None)
        # TODO: Do something with lockfile, same as create()

    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
    return deps_graph
