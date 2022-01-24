import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile, get_profiles_from_args, _add_common_install_arguments
from conans.cli.conan_app import ConanApp
from conans.cli.formatters.graph import print_graph_basic, print_graph_packages
from conans.cli.output import ConanOutput
from conans.client.conanfile.build import run_build_method
from conans.errors import conanfile_exception_formatter
from conans.model.recipe_ref import RecipeReference
from conans.util.files import chdir, mkdir


@conan_command(group=COMMAND_GROUPS['creator'])
def test(conan_api, parser, *args):
    """
    Test a package from a test_package folder
    """
    parser.add_argument("path", action=OnceArgument,
                        help="Path to a test_package folder containing a conanfile.py")
    parser.add_argument("reference", action=OnceArgument,
                        help='Provide a package reference to test')
    _add_common_install_arguments(parser, build_help=False)  # Package must exist
    parser.add_argument("--require-override", action="append",
                        help="Define a requirement override")
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    ref = RecipeReference.loads(args.reference)
    path = _get_conanfile_path(args.path, cwd, py=True)
    lockfile_path = make_abs_path(args.lockfile, cwd)
    lockfile = get_lockfile(lockfile=lockfile_path, strict=False)  # Create is NOT strict!
    remote = conan_api.remotes.get(args.remote) if args.remote else None
    profile_host, profile_build = get_profiles_from_args(conan_api, args)

    out = ConanOutput()
    out.highlight("\n-------- Input profiles ----------")
    out.info("Profile host:")
    out.info(profile_host.dumps())
    out.info("Profile build:")
    out.info(profile_build.dumps())

    root_node = conan_api.graph.load_root_test_conanfile(path, ref,
                                                         profile_host, profile_build,
                                                         require_overrides=args.require_override,
                                                         remote=remote,
                                                         update=args.update,
                                                         lockfile=lockfile)

    out.highlight("-------- Computing dependency graph ----------")
    check_updates = args.check_updates if "check_updates" in args else False
    deps_graph = conan_api.graph.load_graph(root_node, profile_host=profile_host,
                                            profile_build=profile_build,
                                            lockfile=lockfile,
                                            remote=remote,
                                            update=args.update,
                                            check_update=check_updates)
    print_graph_basic(deps_graph)
    out.highlight("\n-------- Computing necessary packages ----------")
    conan_api.graph.analyze_binaries(deps_graph, remote=remote, update=args.update)
    print_graph_packages(deps_graph)

    out.highlight("\n-------- Installing packages ----------")
    conan_api.install.install_binaries(deps_graph=deps_graph,
                                       remote=remote, update=args.update)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        out.info(f"Saving lockfile: {lockfile_out}")
        lockfile.save(lockfile_out)

    out.highlight("\n-------- Testing the package ----------")

    conanfile_folder = os.path.dirname(path)
    conan_api.install.install_consumer(deps_graph=deps_graph, base_folder=cwd,
                                       reference=ref, create_reference=True,
                                       install_folder=conanfile_folder,
                                       conanfile_folder=conanfile_folder)
    conanfile = deps_graph.root.conanfile

    # TODO: This will need to adapt if --build-folder is used
    conanfile.folders.set_base_build(conanfile_folder)
    conanfile.folders.set_base_source(conanfile_folder)
    conanfile.folders.set_base_package(conanfile_folder)
    conanfile.folders.set_base_generators(conanfile_folder)
    conanfile.folders.set_base_install(conanfile_folder)

    out.highlight("\n-------- Testing the package: Building ----------")
    mkdir(conanfile.build_folder)
    with chdir(conanfile.build_folder):
        app = ConanApp(conan_api.cache_folder)
        run_build_method(conanfile, app.hook_manager, conanfile_path=path)

    out.highlight("\n-------- Testing the package: Running test() ----------")
    conanfile.output.highlight("Running test()")
    with conanfile_exception_formatter(conanfile, "test"):
        with chdir(conanfile.build_folder):
            conanfile.test()
