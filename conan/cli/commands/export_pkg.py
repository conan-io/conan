import json
import os

from conan.api.output import cli_out_write
from conan.cli.command import conan_command
from conan.cli.args import add_lockfile_args, add_profiles_args, add_reference_args
from conans.errors import ConanInvalidConfiguration


def json_export_pkg(info):
    deps_graph = info
    cli_out_write(json.dumps({"graph": deps_graph.serialize()}, indent=4))


@conan_command(group="Creator", formatters={"json": json_export_pkg})
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
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)

    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    ref, conanfile = conan_api.export.export(path=path,
                                             name=args.name, version=args.version,
                                             user=args.user, channel=args.channel,
                                             lockfile=lockfile)
    # The package_type is not fully processed at export
    assert conanfile.package_type != "python-require", "A python-require cannot be export-pkg"
    lockfile = conan_api.lockfile.update_lockfile_export(lockfile, conanfile, ref)

    # TODO: Maybe we want to be able to export-pkg it as --build-require
    deps_graph = conan_api.graph.load_graph_consumer(path,
                                                     ref.name, ref.version, ref.user, ref.channel,
                                                     profile_host=profile_host,
                                                     profile_build=profile_build,
                                                     lockfile=lockfile,
                                                     remotes=None,
                                                     update=None)

    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, build_mode=[ref.name], lockfile=lockfile)
    deps_graph.report_graph_error()

    # FIXME: This code is duplicated from install_consumer() from InstallAPI
    root_node = deps_graph.root
    root_node.ref = ref
    conanfile = root_node.conanfile

    if conanfile.info is not None and conanfile.info.invalid:
        binary, reason = "Invalid", conanfile.info.invalid
        msg = "{}: Invalid ID: {}: {}".format(conanfile, binary, reason)
        raise ConanInvalidConfiguration(msg)

    if root_node.cant_build:
        binary, reason = "Cannot build for this configuration", root_node.cant_build
        msg = "{}: {}: {}".format(conanfile, binary, reason)
        raise ConanInvalidConfiguration(msg)

    conan_api.export.export_pkg(deps_graph, path)

    lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
    return deps_graph
