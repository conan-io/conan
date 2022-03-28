import os

from conans.cli.command import conan_command, Extender, COMMAND_GROUPS
from conans.cli.commands import make_abs_path
from conans.cli.common import _add_common_install_arguments, _help_build_policies, \
    get_profiles_from_args, get_lockfile, get_multiple_remotes, add_lockfile_args, \
    add_reference_args, scope_options
from conans.cli.formatters.graph import print_graph_basic, print_graph_packages
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


def _get_conanfile_path(path, cwd, py):
    """
    param py= True: Must be .py, False: Must be .txt, None: Try .py, then .txt
    """
    candidate_paths = list()
    path = make_abs_path(path, cwd)

    if os.path.isdir(path):  # Can be a folder
        if py:
            path = os.path.join(path, "conanfile.py")
            candidate_paths.append(path)
        elif py is False:
            path = os.path.join(path, "conanfile.txt")
            candidate_paths.append(path)
        else:
            path_py = os.path.join(path, "conanfile.py")
            candidate_paths.append(path_py)
            if os.path.exists(path_py):
                path = path_py
            else:
                path = os.path.join(path, "conanfile.txt")
                candidate_paths.append(path)
    else:
        candidate_paths.append(path)

    if not os.path.isfile(path):  # Must exist
        raise ConanException("Conanfile not found at %s" % " or ".join(candidate_paths))

    if py and not path.endswith(".py"):
        raise ConanException("A conanfile.py is needed, " + path + " is not acceptable")

    return path


def graph_compute(args, conan_api, strict=False):
    cwd = os.getcwd()
    lockfile_path = make_abs_path(args.lockfile, cwd)
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None

    requires = [RecipeReference.loads(r) for r in args.requires] \
        if ("requires" in args and args.requires) else None
    tool_requires = [RecipeReference.loads(r) for r in args.tool_requires] \
        if ("tool_requires" in args and args.tool_requires) else None

    if not path and not requires and not tool_requires:
        raise ConanException("Please specify at least a path to a conanfile or a valid reference.")

    # Basic collaborators, remotes, lockfile, profiles
    remotes = get_multiple_remotes(conan_api, args.remote)
    lockfile = get_lockfile(lockfile=lockfile_path, strict=strict)
    profile_host, profile_build = get_profiles_from_args(conan_api, args)

    out = ConanOutput()
    out.highlight("-------- Input profiles ----------")
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

    out.highlight("-------- Computing dependency graph ----------")
    check_updates = args.check_updates if "check_updates" in args else False
    deps_graph = conan_api.graph.load_graph(root_node, profile_host=profile_host,
                                            profile_build=profile_build,
                                            lockfile=lockfile,
                                            remotes=remotes,
                                            update=args.update,
                                            check_update=check_updates)
    print_graph_basic(deps_graph)
    out.highlight("\n-------- Computing necessary packages ----------")
    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    return deps_graph, lockfile


def common_graph_args(subparser):
    subparser.add_argument("path", nargs="?",
                           help="Path to a folder containing a recipe (conanfile.py "
                                "or conanfile.txt) or to a recipe file. e.g., "
                                "./my_project/conanfile.txt.")
    add_reference_args(subparser)
    subparser.add_argument("--requires", action="append",
                           help='Directly provide requires instead of a conanfile')
    subparser.add_argument("--tool-requires", action='append',
                           help='Directly provide tool-requires instead of a conanfile')
    _add_common_install_arguments(subparser, build_help=_help_build_policies.format("never"))
    add_lockfile_args(subparser)


@conan_command(group=COMMAND_GROUPS['consumer'])
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
    parser.add_argument("-g", "--generator", nargs=1, action=Extender,
                        help='Generators to use')
    parser.add_argument("-of", "--output-folder",
                        help='The root output folder for generated and build files')
    parser.add_argument("--deploy", action=Extender,
                        help='Deploy using the provided deployer to the output folder')
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")

    cwd = os.getcwd()
    if args.path:
        path = _get_conanfile_path(args.path, cwd, py=None)
        source_folder = os.path.dirname(path)
    else:
        source_folder = cwd
    if args.output_folder:
        output_folder = make_abs_path(args.output_folder, cwd)
    else:
        output_folder = None

    remote = get_multiple_remotes(conan_api, args.remote)

    deps_graph, lockfile = graph_compute(args, conan_api, strict=args.lockfile_strict)

    out = ConanOutput()
    out.highlight("\n-------- Installing packages ----------")
    conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remote, update=args.update)

    out.highlight("\n-------- Finalizing install (deploy, generators) ----------")
    conan_api.install.install_consumer(deps_graph=deps_graph,
                                       generators=args.generator,
                                       output_folder=output_folder,
                                       source_folder=source_folder,
                                       deploy=args.deploy
                                       )

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        out.info(f"Saving lockfile: {lockfile_out}")
        lockfile.save(lockfile_out)
