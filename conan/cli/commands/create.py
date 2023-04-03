import json
import os
import shutil

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.cli.commands.export import common_args_export
from conan.cli.args import add_lockfile_args, add_common_install_arguments
from conan.cli.printers import print_profiles
from conan.cli.printers.graph import print_graph_packages, print_graph_basic
from conan.errors import ConanException
from conans.util.files import mkdir


def json_create(deps_graph):
    if deps_graph is None:
        return
    cli_out_write(json.dumps({"graph": deps_graph.serialize()}, indent=4))


@conan_command(group="Creator", formatters={"json": json_create})
def create(conan_api, parser, *args):
    """
    Create a package.
    """
    common_args_export(parser)
    add_lockfile_args(parser)
    add_common_install_arguments(parser)
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided reference is a build-require')
    parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                        help='Alternative test folder name. By default it is "test_package". '
                             'Use "" to skip the test stage')
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    test_conanfile_path = _get_test_conanfile_path(args.test_folder, path)

    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    ref, conanfile = conan_api.export.export(path=path,
                                             name=args.name, version=args.version,
                                             user=args.user, channel=args.channel,
                                             lockfile=lockfile,
                                             remotes=remotes)
    # The package_type is not fully processed at export
    is_python_require = conanfile.package_type == "python-require"
    lockfile = conan_api.lockfile.update_lockfile_export(lockfile, conanfile, ref,
                                                         args.build_require)

    print_profiles(profile_host, profile_build)

    deps_graph = None
    if not is_python_require:
        # TODO: This section might be overlapping with ``graph_compute()``
        requires = [ref] if not args.build_require else None
        tool_requires = [ref] if args.build_require else None
        # FIXME: Dirty: package type still raw, not processed yet
        # TODO: Why not for package_type = "application" like cmake to be used as build-require?
        if conanfile.package_type == "build-scripts" and not args.build_require:
            # swap them
            requires, tool_requires = tool_requires, requires
        deps_graph = conan_api.graph.load_graph_requires(requires, tool_requires,
                                                         profile_host=profile_host,
                                                         profile_build=profile_build,
                                                         lockfile=lockfile,
                                                         remotes=remotes, update=args.update)
        print_graph_basic(deps_graph)
        deps_graph.report_graph_error()

        # Not specified, force build the tested library
        build_modes = [ref.repr_notime()] if args.build is None else args.build
        conan_api.graph.analyze_binaries(deps_graph, build_modes, remotes=remotes,
                                         update=args.update, lockfile=lockfile)
        print_graph_packages(deps_graph)

        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)
        # We update the lockfile, so it will be updated for later ``test_package``
        lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                      clean=args.lockfile_clean)

    if test_conanfile_path:
        # TODO: We need arguments for:
        #  - decide update policy "--test_package_update"
        tested_python_requires = ref.repr_notime() if is_python_require else None
        from conan.cli.commands.test import run_test
        deps_graph = run_test(conan_api, test_conanfile_path, ref, profile_host, profile_build,
                              remotes, lockfile, update=False, build_modes=args.build,
                              tested_python_requires=tested_python_requires)
        lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                      clean=args.lockfile_clean)

    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
    return deps_graph


def _check_tested_reference_matches(deps_graph, tested_ref, out):
    """ Check the test_profile_override_conflict test. If we are testing a build require
    but we specify the build require with a different version in the profile, it has priority,
    it is correct but weird and likely a mistake"""
    # https://github.com/conan-io/conan/issues/10453
    direct_refs = [n.conanfile.ref for n in deps_graph.root.neighbors()]
    # There is a reference with same name but different
    missmatch = [ref for ref in direct_refs if ref.name == tested_ref.name and ref != tested_ref]
    if missmatch:
        out.warning("The package created was '{}' but the reference being "
                    "tested is '{}'".format(missmatch[0], tested_ref))


def test_package(conan_api, deps_graph, test_conanfile_path, tested_python_requires=None):
    out = ConanOutput()
    out.title("Testing the package")
    # TODO: Better modeling when we are testing a python_requires
    if len(deps_graph.nodes) == 1 and not tested_python_requires:
        raise ConanException("The conanfile at '{}' doesn't declare any requirement, "
                             "use `self.tested_reference_str` to require the "
                             "package being created.".format(test_conanfile_path))
    conanfile_folder = os.path.dirname(test_conanfile_path)
    conanfile = deps_graph.root.conanfile
    # To make sure the folders are correct
    conanfile.folders.set_base_folders(conanfile_folder, output_folder=None)
    if conanfile.build_folder and conanfile.build_folder != conanfile.source_folder:
        # should be the same as build folder, but we can remove it
        out.info("Removing previously existing 'test_package' build folder: "
                 f"{conanfile.build_folder}")
        shutil.rmtree(conanfile.build_folder, ignore_errors=True)
        mkdir(conanfile.build_folder)
    conanfile.output.info(f"Test package build: {conanfile.folders.build}")
    conanfile.output.info(f"Test package build folder: {conanfile.build_folder}")
    conan_api.install.install_consumer(deps_graph=deps_graph,
                                       source_folder=conanfile_folder)

    out.title("Testing the package: Building")
    conan_api.local.build(conanfile)

    out.title("Testing the package: Executing test")
    conanfile.output.highlight("Running test()")
    conan_api.local.test(conanfile)


def _get_test_conanfile_path(tf, conanfile_path):
    """Searches in the declared test_folder or in the standard "test_package"
    """
    if tf == "":  # Now if parameter --test-folder="" we have to skip tests
        return None
    base_folder = os.path.dirname(conanfile_path)
    test_conanfile_path = os.path.join(base_folder, tf or "test_package", "conanfile.py")
    if os.path.exists(test_conanfile_path):
        return test_conanfile_path
    elif tf:
        raise ConanException(f"test folder '{tf}' not available, or it doesn't have a conanfile.py")
