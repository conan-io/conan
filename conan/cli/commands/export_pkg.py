import json
import os

from conan.cli.command import conan_command, COMMAND_GROUPS
from conan.cli.commands.install import _get_conanfile_path
from conan.cli.common import get_lockfile, add_profiles_args, get_profiles_from_args, \
    add_lockfile_args, add_reference_args, scope_options, save_lockfile_out


def json_export_pkg(info):
    deps_graph = info
    return json.dumps({"graph": deps_graph.serialize()}, indent=4)


@conan_command(group=COMMAND_GROUPS['creator'], formatters={"json": json_export_pkg})
def export_pkg(conan_api, parser, *args):
    """
    Export recipe to the Conan package cache, and create a package directly from pre-compiled binaries
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    add_reference_args(parser)
    add_lockfile_args(parser)
    add_profiles_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = _get_conanfile_path(args.path, cwd, py=True)
    lockfile = get_lockfile(lockfile_path=args.lockfile, cwd=cwd, conanfile_path=path,
                            partial=args.lockfile_partial)

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
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, build_mode=[ref.name], lockfile=lockfile)
    deps_graph.report_graph_error()

    conan_api.export.export_pkg(deps_graph, path)

    save_lockfile_out(args, deps_graph, lockfile, cwd)
    return deps_graph
