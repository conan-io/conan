import json
import os

from conan.api.conan_api import ConanAPI
from conan.api.output import ConanOutput, cli_out_write
from conan.api.subapi.workspace import WorkspaceAPI
from conan.cli import make_abs_path
from conan.cli.args import add_reference_args, add_common_install_arguments, add_lockfile_args
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands.list import print_serial
from conan.cli.printers import print_profiles
from conan.cli.printers.graph import print_graph_packages, print_graph_basic
from conan.errors import ConanException


@conan_subcommand(formatters={"text": cli_out_write})
def workspace_root(conan_api: ConanAPI, parser, subparser, *args):  # noqa
    """
    Return the folder containing the conanws.py/conanws.yml workspace file
    """
    ws = conan_api.workspace
    if not ws.folder():
        raise ConanException("No workspace defined, conanws.py file not found")
    return ws.folder()


@conan_subcommand()
def workspace_open(conan_api: ConanAPI, parser, subparser, *args):
    """
    Open specific references
    """
    subparser.add_argument("reference",
                           help="Open this package source repository")
    group = subparser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')
    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    cwd = os.getcwd()
    conan_api.workspace.open(args.reference, remotes=remotes, cwd=cwd)


@conan_subcommand()
def workspace_add(conan_api: ConanAPI, parser, subparser, *args):
    """
    Add packages to current workspace
    """
    subparser.add_argument('path',  nargs="?",
                           help='Path to the package folder in the user workspace')
    add_reference_args(subparser)
    subparser.add_argument("--ref", help="Open and add this reference")
    subparser.add_argument("-of", "--output-folder",
                           help='The root output folder for generated and build files')
    group = subparser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')
    subparser.add_argument("--product", action="store_true", help="Add the package as a product")
    args = parser.parse_args(*args)
    if args.path and args.ref:
        raise ConanException("Do not use both 'path' and '--ref' argument")
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    cwd = os.getcwd()
    path = args.path
    if args.ref:
        # TODO: Use path here to open in this path
        path = conan_api.workspace.open(args.ref, remotes, cwd=cwd)
    ref = conan_api.workspace.add(path,
                                  args.name, args.version, args.user, args.channel,
                                  cwd, args.output_folder, remotes=remotes, product=args.product)
    ConanOutput().success("Reference '{}' added to workspace".format(ref))


@conan_subcommand()
def workspace_remove(conan_api: ConanAPI, parser, subparser, *args):
    """
    Remove packages from the current workspace
    """
    subparser.add_argument('path',
                           help='Path to the package folder in the user workspace')
    args = parser.parse_args(*args)
    removed = conan_api.workspace.remove(make_abs_path(args.path))
    ConanOutput().info(f"Removed from workspace: {removed}")


def print_json(data):
    results = data["info"]
    myjson = json.dumps(results, indent=4)
    cli_out_write(myjson)


def _print_workspace_info(data):
    print_serial(data["info"])


@conan_subcommand(formatters={"text": _print_workspace_info, "json": print_json})
def workspace_info(conan_api: ConanAPI, parser, subparser, *args):  # noqa
    """
    Display info for current workspace
    """
    return {"info": conan_api.workspace.info()}


@conan_subcommand()
def workspace_build(conan_api: ConanAPI, parser, subparser, *args):
    """
    Build the current workspace, starting from the "products"
    """
    subparser.add_argument("path", nargs="?",
                           help='Path to a package folder in the user workspace')
    add_common_install_arguments(subparser)
    add_lockfile_args(subparser)
    args = parser.parse_args(*args)
    # Basic collaborators: remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    # The lockfile by default if not defined will be read from the root workspace folder
    ws_folder = conan_api.workspace.folder()
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, conanfile_path=ws_folder,
                                               cwd=None,
                                               partial=args.lockfile_partial, overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)
    print_profiles(profile_host, profile_build)

    build_mode = args.build or []
    if "editable" not in build_mode:
        ConanOutput().info("Adding '--build=editable' as build mode")
        build_mode.append("editable")

    if args.path:
        products = [args.path]
    else:  # all products
        products = conan_api.workspace.products
        if not products:
            raise ConanException("There are no products defined in the workspace, can't build\n"
                                 "You can use 'conan build <path> --build=editable' to build")
        ConanOutput().title(f"Building workspace products {products}")

    editables = conan_api.workspace.editable_packages
    # TODO: This has to be improved to avoid repetition when there are multiple products
    for product in products:
        ConanOutput().subtitle(f"Building workspace product: {product}")
        product_ref = conan_api.workspace.editable_from_path(product)
        if product_ref is None:
            raise ConanException(f"Product '{product}' not defined in the workspace as editable")
        editable = editables[product_ref]
        editable_path = editable["path"]
        deps_graph = conan_api.graph.load_graph_consumer(editable_path, None, None, None, None,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update)
        deps_graph.report_graph_error()
        print_graph_basic(deps_graph)
        conan_api.graph.analyze_binaries(deps_graph, build_mode, remotes=remotes, update=args.update,
                                         lockfile=lockfile)
        print_graph_packages(deps_graph)
        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)
        conan_api.install.install_consumer(deps_graph, None, os.path.dirname(editable_path),
                                           editable.get("output_folder"))
        ConanOutput().title(f"Calling build() for the product {product_ref}")
        conanfile = deps_graph.root.conanfile
        conan_api.local.build(conanfile)


@conan_subcommand()
def workspace_install(conan_api: ConanAPI, parser, subparser, *args):
    """
    Install the workspace as a monolith, installing only external dependencies to the workspace,
    generating a single result (generators, etc) for the whole workspace.
    """
    subparser.add_argument("path", nargs="*",
                           help="Install only these editable packages, not all")
    subparser.add_argument("-g", "--generator", action="append", help='Generators to use')
    subparser.add_argument("-of", "--output-folder",
                           help='The root output folder for generated and build files')
    subparser.add_argument("--envs-generation", default=None, choices=["false"],
                           help="Generation strategy for virtual environment files for the root")
    add_common_install_arguments(subparser)
    add_lockfile_args(subparser)
    args = parser.parse_args(*args)
    # Basic collaborators: remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    # The lockfile by default if not defined will be read from the root workspace folder
    ws_folder = conan_api.workspace.folder()
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, conanfile_path=ws_folder,
                                               cwd=None,
                                               partial=args.lockfile_partial, overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)
    print_profiles(profile_host, profile_build)

    conan_api.workspace.info()  # FIXME: Just to force error if WS not enabled
    # Build a dependency graph with all editables as requirements
    requires = conan_api.workspace.select_editables(args.path)
    if not requires:
        raise ConanException("This workspace cannot be installed, it doesn't have any editable")
    deps_graph = conan_api.graph.load_graph_requires(requires, [],
                                                     profile_host, profile_build, lockfile,
                                                     remotes, args.build, args.update)
    deps_graph.report_graph_error()
    print_graph_basic(deps_graph)

    # Collapsing the graph
    ws_graph = conan_api.workspace.collapse_editables(deps_graph, profile_host, profile_build)
    ConanOutput().subtitle("Collapsed graph")
    print_graph_basic(ws_graph)

    conan_api.graph.analyze_binaries(ws_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(ws_graph)
    conan_api.install.install_binaries(deps_graph=ws_graph, remotes=remotes)
    output_folder = make_abs_path(args.output_folder) if args.output_folder else None
    conan_api.install.install_consumer(ws_graph, args.generator, ws_folder, output_folder,
                                       envs_generation=args.envs_generation)


@conan_command(group="Consumer")
def workspace(conan_api, parser, *args):  # noqa
    """
    Manage Conan workspaces (group of packages in editable mode)
    """
    if (WorkspaceAPI.TEST_ENABLED or os.getenv("CONAN_WORKSPACE_ENABLE")) != "will_break_next":
        raise ConanException("Workspace command disabled without CONAN_WORKSPACE_ENABLE env var,"
                             "please read the docs about this 'incubating' feature")
