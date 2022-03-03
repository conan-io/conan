from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument, \
    conan_subcommand
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import common_graph_args, graph_compute
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.model.graph_lock import Lockfile


@conan_command(group=COMMAND_GROUPS['consumer'])
def lock(conan_api, parser, *args):
    """
    Create or manages lockfiles
    """


@conan_subcommand()
def lock_create(conan_api, parser, subparser, *args):
    """
    Create a lockfile from a conanfile or a reference
    """
    common_graph_args(subparser)
    subparser.add_argument("--clean", action="store_true", help="remove unused")

    args = parser.parse_args(*args)

    # parameter validation
    if args.reference and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--reference")

    deps_graph, lockfile = graph_compute(args, conan_api, strict=False)

    if lockfile is None or args.clean:
        lockfile = Lockfile(deps_graph)
    else:
        lockfile.update_lock(deps_graph)

    lockfile_out = make_abs_path(args.lockfile_out or "conan.lock")
    lockfile.save(lockfile_out)
    ConanOutput().info("Generated lockfile: %s" % lockfile_out)


@conan_subcommand()
def lock_merge(conan_api, parser, subparser, *args):
    """
    Merge 2 or more lockfiles
    """
    subparser.add_argument('--lockfile', action="append", help='Path to lockfile to be merged')
    subparser.add_argument("--lockfile-out", action=OnceArgument, default="conan.lock",
                           help="Filename of the created lockfile")

    args = parser.parse_args(*args)

    result = Lockfile()
    for lockfile in args.lockfile:
        lockfile = make_abs_path(lockfile)
        graph_lock = Lockfile.load(lockfile)
        result.merge(graph_lock)

    lockfile_out = make_abs_path(args.lockfile_out)
    result.save(lockfile_out)
    ConanOutput().info("Generated lockfile: %s" % lockfile_out)
