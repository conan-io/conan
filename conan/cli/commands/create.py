import json
import os
import shutil

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.cli.commands.export import common_args_export
from conan.cli.args import add_lockfile_args, _add_common_install_arguments, _help_build_policies
from conan.internal.conan_app import ConanApp
from conan.cli.printers.graph import print_graph_packages
from conans.client.conanfile.build import run_build_method
from conans.errors import ConanException, conanfile_exception_formatter
from conans.util.files import chdir, mkdir


def json_create(deps_graph):
    if deps_graph is None:
        return
    cli_out_write(json.dumps({"graph": deps_graph.serialize()}, indent=4))


@conan_command(group="Creator", formatters={"json": json_create})
def create(conan_api, parser, *args):
    """
    Create a package
    """
    common_args_export(parser)
    add_lockfile_args(parser)
    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='The provided reference is a build-require')
    parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                        help='Alternative test folder name. By default it is "test_package". '
                             'Use "None" to skip the test stage')
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    # Now if parameter --test-folder=None (string None) we have to skip tests
    test_folder = False if args.test_folder == "None" else args.test_folder
    test_conanfile_path = _get_test_conanfile_path(test_folder, path)

    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
    remotes = conan_api.remotes.list(args.remote)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    out = ConanOutput()
    out.highlight("Exporting the recipe")
    ref, conanfile = conan_api.export.export(path=path,
                                             name=args.name, version=args.version,
                                             user=args.user, channel=args.channel,
                                             lockfile=lockfile,
                                             remotes=remotes)
    # The package_type is not fully processed at export
    is_python_require = conanfile.package_type == "python-require"
    lockfile = conan_api.lockfile.update_lockfile_export(lockfile, conanfile, ref,
                                                         args.build_require)

    out.title("Input profiles")
    out.info("Profile host:")
    out.info(profile_host.dumps())
    out.info("Profile build:")
    out.info(profile_build.dumps())

    deps_graph = None
    if not is_python_require:
        # TODO: This section might be overlapping with ``graph_compute()``
        requires = [ref] if not args.build_require else None
        tool_requires = [ref] if args.build_require else None

        out.title("Computing dependency graph")
        deps_graph = conan_api.graph.load_graph_requires(requires, tool_requires,
                                                         profile_host=profile_host,
                                                         profile_build=profile_build,
                                                         lockfile=lockfile,
                                                         remotes=remotes, update=args.update)
        deps_graph.report_graph_error()

        out.title("Computing necessary packages")
        # Not specified, force build the tested library
        build_modes = [ref.repr_notime()] if args.build is None else args.build
        conan_api.graph.analyze_binaries(deps_graph, build_modes, remotes=remotes,
                                         update=args.update, lockfile=lockfile)
        print_graph_packages(deps_graph)

        out.title("Installing packages")
        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes,
                                           update=args.update)
        # We update the lockfile, so it will be updated for later ``test_package``
        lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                      clean=args.lockfile_clean)

    if test_conanfile_path:
        # TODO: We need arguments for:
        #  - decide build policy for test_package deps "--test_package_build=missing"
        #  - decide update policy "--test_package_update"
        tested_python_requires = ref.repr_notime() if is_python_require else None
        from conan.cli.commands.test import run_test
        deps_graph = run_test(conan_api, test_conanfile_path, ref, profile_host, profile_build,
                              remotes, lockfile, update=False, build_modes=None,
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
    output_folder = os.path.join(conanfile_folder, conanfile.folders.test_output)
    if conanfile.folders.test_output:
        shutil.rmtree(output_folder, ignore_errors=True)
        mkdir(output_folder)
    conan_api.install.install_consumer(deps_graph=deps_graph,
                                       source_folder=conanfile_folder,
                                       output_folder=output_folder)

    out.title("Testing the package: Building")
    app = ConanApp(conan_api.cache_folder)
    conanfile.folders.set_base_package(conanfile.folders.base_build)
    run_build_method(conanfile, app.hook_manager)

    out.title("Testing the package: Running test()")
    conanfile.output.highlight("Running test()")
    with conanfile_exception_formatter(conanfile, "test"):
        with chdir(conanfile.build_folder):
            conanfile.test()


def _get_test_conanfile_path(tf, conanfile_path):
    """Searches in the declared test_folder or in the standard "test_package"
    """

    if tf is False:
        # Look up for testing conanfile can be disabled if tf (test folder) is False
        return None

    base_folder = os.path.dirname(conanfile_path)
    test_conanfile_path = os.path.join(base_folder, tf or "test_package", "conanfile.py")
    if os.path.exists(test_conanfile_path):
        return test_conanfile_path
    if tf:
        raise ConanException("test folder '{tf}' not available, or it doesn't have a conanfile.py")
