import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile, add_profiles_args, get_profiles_from_args, \
    add_lockfile_args, add_reference_args, scope_options


@conan_command(group=COMMAND_GROUPS['creator'])
def export_pkg(conan_api, parser, *args, **kwargs):
    """
    Export recipe to the Conan package cache
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    add_reference_args(parser)
    add_lockfile_args(parser)
    add_profiles_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    lockfile_path = make_abs_path(args.lockfile, cwd)
    lockfile = get_lockfile(lockfile=lockfile_path, strict=args.lockfile_strict)
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None
    profile_host, profile_build = get_profiles_from_args(conan_api, args)

    ref = conan_api.export.export(path=path,
                                  name=args.name,
                                  version=args.version,
                                  user=args.user,
                                  channel=args.channel,
                                  lockfile=lockfile)

    # TODO: Maybe we want to be able to export-pkg it as --build-require
    scope_options(profile_host, requires=[ref], tool_requires=None)
    root_node = conan_api.graph.load_root_virtual_conanfile(requires=[ref],
                                                            profile_host=profile_host)
    deps_graph = conan_api.graph.load_graph(root_node, profile_host=profile_host,
                                            profile_build=profile_build,
                                            lockfile=lockfile,
                                            remotes=None,
                                            update=None)
    conan_api.graph.analyze_binaries(deps_graph, build_mode=[ref.name], lockfile=lockfile)
    deps_graph.report_graph_error()

    conan_api.export.export_pkg(deps_graph, path)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        lockfile.save(lockfile_out)
