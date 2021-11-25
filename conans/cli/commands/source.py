import os

from conans.cli.command import conan_command, Extender, COMMAND_GROUPS, OnceArgument
from conans.cli.common import _add_common_install_arguments, _help_build_policies, \
    get_profiles_from_args, get_lockfile
from conans.client.conan_api import _make_abs_path
from conans.client.graph.printer import print_graph
from conans.client.source import run_source_method
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
def source(conan_api, parser, *args, **kwargs):
    """
    source api
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py "
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
    parser.add_argument("-if", "--install-folder", action=OnceArgument,
                        help='Use this directory as the directory where to put the generator'
                             'files.')

    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    install_folder = _make_abs_path(args.install_folder, cwd)
    path = _get_conanfile_path(args.path, cwd, py=True) if args.path else None

    # Basic collaborators, remotes, lockfile, profiles
    remote = conan_api.remotes.get(args.remote) if args.remote else None
    profile_host, profile_build = get_profiles_from_args(conan_api, args)
    root_ref = RecipeReference(name=args.name, version=args.version,
                               user=args.user, channel=args.channel)

    # TODO: Discuss: This could be further split into graph + binary-analyzer
    deps_graph = conan_api.graph.load_graph(path=path,
                                            profile_host=profile_host,
                                            profile_build=profile_build,
                                            root_ref=root_ref,
                                            reference=None,
                                            lockfile=None,
                                            remote=remote)

    conanfile = deps_graph.root.conanfile
    conanfile.folders.set_base_source(install_folder)
    conanfile.folders.set_base_build(None)
    conanfile.folders.set_base_package(None)

    run_source_method(conanfile)
