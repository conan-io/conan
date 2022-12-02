import json
import os

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command
from conan.cli.commands import make_abs_path
from conan.cli.common import scope_options
from conan.cli.args import common_graph_args
from conan.cli.printers.graph import print_graph_basic, print_graph_packages

from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


def json_install(info):
    deps_graph = info
    cli_out_write(json.dumps({"graph": deps_graph.serialize()}, indent=4))


def graph_compute(args, conan_api, partial=False, allow_error=False):
    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    requires = [RecipeReference.loads(r) for r in args.requires] \
        if ("requires" in args and args.requires) else None
    tool_requires = [RecipeReference.loads(r) for r in args.tool_requires] \
        if ("tool_requires" in args and args.tool_requires) else None

    if not path and not requires and not tool_requires:
        raise ConanException("Please specify at least a path to a conanfile or a valid reference.")

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=partial)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    out = ConanOutput()
    out.title("Input profiles")
    out.info("Profile host:")
    out.info(profile_host.dumps())
    out.info("Profile build:")
    out.info(profile_build.dumps())

    if path is not None:
        root_node = conan_api.graph.load_root_consumer_conanfile(path, profile_host, profile_build,
                                                                 name=args.name,
                                                                 version=args.version,
                                                                 user=args.user,
                                                                 channel=args.channel,
                                                                 lockfile=lockfile,
                                                                 remotes=remotes,
                                                                 update=args.update)
    else:
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
    if deps_graph.error:
        if allow_error:
            return deps_graph, lockfile
        raise deps_graph.error

    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    return deps_graph, lockfile


@conan_command(group="Consumer", formatters={"json": json_install})
def install(conan_api, parser, *args):
    """
    Installs the requirements specified in a recipe (conanfile.py or conanfile.txt).

    It can also be used to install a concrete package specifying a
    reference. If any requirement is not found in the local cache, it will
    retrieve the recipe from a remote, looking for it sequentially in the
    configured remotes. When the recipes have been downloaded it will try
    to download a binary package matching the specified settings, only from
    the remote from which the recipe was retrieved. If no binary package is
    found, it can be built from sources using the '--build' option. When
    the package is installed, Conan will write the files for the specified
    generators.
    """
    common_graph_args(parser)
    parser.add_argument("-g", "--generator", action="append",
                        help='Generators to use')
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    parser.add_argument("--deploy", action="append",
                        help='Deploy using the provided deployer to the output folder')
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")

    cwd = os.getcwd()
    if args.path:
        path = conan_api.local.get_conanfile_path(args.path, cwd, py=None)
        source_folder = os.path.dirname(path)
    else:
        source_folder = cwd
    if args.output_folder:
        output_folder = make_abs_path(args.output_folder, cwd)
    else:
        output_folder = None

    remotes = conan_api.remotes.list(args.remote)

    deps_graph, lockfile = graph_compute(args, conan_api, partial=args.lockfile_partial)

    out = ConanOutput()
    out.title("Installing packages")
    conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes, update=args.update)

    out.title("Finalizing install (deploy, generators)")
    conan_api.install.install_consumer(deps_graph=deps_graph,
                                       generators=args.generator,
                                       output_folder=output_folder,
                                       source_folder=source_folder,
                                       deploy=args.deploy
                                       )

    lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
    return deps_graph
