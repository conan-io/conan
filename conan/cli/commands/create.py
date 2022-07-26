import json
import os
import shutil

from conan.api.output import ConanOutput
from conan.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conan.cli.commands.export import common_args_export
from conan.cli.commands.install import _get_conanfile_path
from conan.cli.common import get_lockfile, get_profiles_from_args, _add_common_install_arguments, \
    _help_build_policies, get_multiple_remotes, add_lockfile_args, scope_options, save_lockfile_out
from conan.api.conan_app import ConanApp
from conan.cli.formatters.graph import print_graph_basic, print_graph_packages
from conans.client.conanfile.build import run_build_method
from conans.errors import ConanException, conanfile_exception_formatter
from conans.util.files import chdir, mkdir


def json_create(info):
    deps_graph = info
    return json.dumps({"graph": deps_graph.serialize()}, indent=4)


@conan_command(group=COMMAND_GROUPS['creator'], formatters={"json": json_create})
def create(conan_api, parser, *args):
    """
    Create a package
    """
    common_args_export(parser)
    add_lockfile_args(parser)
    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='The provided reference is a build-require')
    parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                        help='Working directory for the build of the test project.')
    parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                        help='Alternative test folder name. By default it is "test_package". '
                             'Use "None" to skip the test stage')
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = _get_conanfile_path(args.path, cwd, py=True)
    lockfile = get_lockfile(lockfile_path=args.lockfile, cwd=cwd, conanfile_path=path,
                            partial=args.lockfile_partial)
    remotes = get_multiple_remotes(conan_api, args.remote)
    profile_host, profile_build = get_profiles_from_args(conan_api, args)

    out = ConanOutput()
    out.highlight("Exporting the recipe")
    ref = conan_api.export.export(path=path,
                                  name=args.name, version=args.version,
                                  user=args.user, channel=args.channel,
                                  lockfile=lockfile)
    if lockfile:
        # FIXME: We need to update build_requires too, not only ``requires``
        lockfile.add(requires=[ref])

    out.title("Input profiles")
    out.info("Profile host:")
    out.info(profile_host.dumps())
    out.info("Profile build:")
    out.info(profile_build.dumps())

    if args.test_folder == "None":
        # Now if parameter --test-folder=None (string None) we have to skip tests
        args.test_folder = False
    test_conanfile_path = _get_test_conanfile_path(args.test_folder, path)
    if test_conanfile_path:
        if args.build_require:
            raise ConanException("--build-require should not be specified, test_package does it")
        root_node = conan_api.graph.load_root_test_conanfile(test_conanfile_path, ref,
                                                             profile_host, profile_build,
                                                             remotes=remotes,
                                                             update=args.update,
                                                             lockfile=lockfile)
    else:
        requires = [ref] if not args.build_require else None
        tool_requires = [ref] if args.build_require else None
        scope_options(profile_host, requires=requires, tool_requires=tool_requires)
        root_node = conan_api.graph.load_root_virtual_conanfile(requires=requires,
                                                                tool_requires=tool_requires,
                                                                profile_host=profile_host)

    out.title("Computing dependency graph")
    check_updates = args.check_updates if "check_updates" in args else False
    deps_graph = conan_api.graph.load_graph(root_node, profile_host=profile_host,
                                            profile_build=profile_build,
                                            lockfile=lockfile,
                                            remotes=remotes,
                                            update=args.update,
                                            check_update=check_updates)
    print_graph_basic(deps_graph)
    out.title("Computing necessary packages")
    if args.build is None:  # Not specified, force build the tested library
        build_modes = [ref.repr_notime()]
    else:
        build_modes = args.build
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, build_modes, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    out.title("Installing packages")
    conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes, update=args.update)

    save_lockfile_out(args, deps_graph, lockfile, cwd)

    if test_conanfile_path:
        _check_tested_reference_matches(deps_graph, ref, out)
        test_package(conan_api, deps_graph, test_conanfile_path)

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


def test_package(conan_api, deps_graph, test_conanfile_path):
    out = ConanOutput()
    out.title("Testing the package")
    if len(deps_graph.nodes) == 1:
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
    """Searches in the declared test_folder or in the standard locations"""

    if tf is False:
        # Look up for testing conanfile can be disabled if tf (test folder) is False
        return None

    test_folders = [tf] if tf else ["test_package", "test"]
    base_folder = os.path.dirname(conanfile_path)
    for test_folder_name in test_folders:
        test_folder = os.path.join(base_folder, test_folder_name)
        test_conanfile_path = os.path.join(test_folder, "conanfile.py")
        if os.path.exists(test_conanfile_path):
            return test_conanfile_path
    else:
        if tf:
            raise ConanException("test folder '%s' not available, or it doesn't have a conanfile.py"
                                 % tf)
