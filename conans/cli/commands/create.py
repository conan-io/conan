import os

from conans.cli.command import conan_command, COMMAND_GROUPS
from conans.cli.commands import make_abs_path
from conans.cli.commands.export import common_args_export
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile, get_profiles_from_args, _add_common_install_arguments, \
    _help_build_policies
from conans.cli.formatters.graph import print_graph_basic, print_graph_packages
from conans.cli.output import ConanOutput
from conans.client.graph.printer import print_graph


@conan_command(group=COMMAND_GROUPS['creator'])
def create(conan_api, parser, *args):
    """
    Create a package
    """
    common_args_export(parser)
    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"),
                                  lockfile=False)
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='The provided reference is a build-require')
    parser.add_argument("--require-override", action="append",
                        help="Define a requirement override")
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = _get_conanfile_path(args.path, cwd, py=True) if args.path else None
    lockfile_path = make_abs_path(args.lockfile, cwd)
    lockfile = get_lockfile(lockfile=lockfile_path, strict=False)  # Create is NOT strict!
    remote = conan_api.remotes.get(args.remote) if args.remote else None
    profile_host, profile_build = get_profiles_from_args(conan_api, args)

    out = ConanOutput()
    out.highlight("-------- Exporting the recipe ----------")
    ref = conan_api.export.export(path=path,
                                  name=args.name, version=args.version,
                                  user=args.user, channel=args.channel,
                                  lockfile=lockfile,
                                  ignore_dirty=args.ignore_dirty)

    out.highlight("-------- Input profiles ----------")
    out.info("Profile host:")
    out.info(profile_host.dumps())
    out.info("Profile build:")
    out.info(profile_build.dumps())

    # decoupling the most complex part, which is loading the root_node, this is the point where
    # the difference between "reference", "path", etc
    root_node = conan_api.graph.load_root_node(ref, None, profile_host, profile_build,
                                               lockfile, root_ref=None,
                                               create_reference=None,
                                               is_build_require=args.build_require,
                                               require_overrides=args.require_override,
                                               remote=remote,
                                               update=args.update)

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
    if args.build is None:  # Not specified, force build the tested library
        build_modes = [ref.name]
    else:
        build_modes = args.build
    conan_api.graph.analyze_binaries(deps_graph, build_modes, remote=remote, update=args.update)
    print_graph_packages(deps_graph)

    # TODO: Keeping old printing to avoid many tests fail: TO REMOVE
    out.highlight("\nLegacy graph output (to be removed):")
    print_graph(deps_graph)

    out.highlight("\n-------- Installing packages ----------")
    conan_api.install.install_binaries(deps_graph=deps_graph, build_modes=args.build,
                                       remote=remote, update=args.update)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        out.info(f"Saving lockfile: {lockfile_out}")
        lockfile.save(lockfile_out)
