import os

from conans.cli.command import conan_command, Extender, COMMAND_GROUPS, OnceArgument
from conans.cli.common import _add_common_install_arguments, _help_build_policies, \
    get_profiles_from_args, get_lockfile
from conans.client.conan_api import _make_abs_path
from conans.client.graph.printer import print_graph
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


def _get_conanfile_path(path, cwd, py):
    """
    param py= True: Must be .py, False: Must be .txt, None: Try .py, then .txt
    """
    candidate_paths = list()
    path = _make_abs_path(path, cwd)

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


@conan_command(group=COMMAND_GROUPS['consumer'])
def install(conan_api, parser, *args, **kwargs):
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
    parser.add_argument("path", nargs="?", help="Path to a folder containing a recipe (conanfile.py "
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

    parser.add_argument("--reference", action=OnceArgument,
                        help='Provide a package reference instead of a conanfile')

    parser.add_argument("-g", "--generator", nargs=1, action=Extender,
                        help='Generators to use')
    parser.add_argument("-if", "--install-folder", action=OnceArgument,
                        help='Use this directory as the directory where to put the generator'
                             'files.')

    parser.add_argument("--no-imports", action='store_true', default=False,
                        help='Install specified packages but avoid running imports')
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='The provided reference is a build-require')

    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
    parser.add_argument("--require-override", action="append",
                        help="Define a requirement override")

    args = parser.parse_args(*args)

    # parameter validation
    if args.reference and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--reference")
    cwd = os.getcwd()
    install_folder = _make_abs_path(args.install_folder, cwd)
    lockfile_path = _make_abs_path(args.lockfile, cwd) if args.lockfile else None
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None
    conanfile_folder = os.path.dirname(path) if path else None
    reference = RecipeReference.loads(args.reference) if args.reference else None
    if not path and not reference:
        raise ConanException("Please specify at least a path to a conanfile or a valid reference.")

    # Basic collaborators, remotes, lockfile, profiles
    remote = conan_api.remotes.get(args.remote) if args.remote else None
    lockfile = get_lockfile(lockfile=lockfile_path, strict=True)
    profile_host, profile_build = get_profiles_from_args(conan_api, args)
    root_ref = RecipeReference(name=args.name, version=args.version,
                               user=args.user, channel=args.channel)

    # TODO: Discuss: This could be further split into graph + binary-analyzer
    deps_graph = conan_api.graph.load_graph(reference=reference,
                                            path=path,
                                            profile_host=profile_host,
                                            profile_build=profile_build,
                                            lockfile=lockfile,
                                            root_ref=root_ref,
                                            build_modes=args.build,
                                            is_build_require=args.build_require,
                                            require_overrides=args.require_override,
                                            remote=remote,
                                            update=args.update)
    print_graph(deps_graph)
    conan_api.install.install_binaries(deps_graph=deps_graph, build_modes=args.build,
                                       remote=remote, update=args.update)
    conan_api.install.install_consumer(deps_graph=deps_graph, base_folder=cwd, reference=reference,
                                       install_folder=install_folder, generators=args.generator,
                                       no_imports=args.no_imports, conanfile_folder=conanfile_folder)
    if args.lockfile_out:
        lockfile_out = _make_abs_path(args.lockfile_out, cwd)
        lockfile.save(lockfile_out)
