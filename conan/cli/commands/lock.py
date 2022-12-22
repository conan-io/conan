import os

from conan.api.output import ConanOutput
from conan.cli.command import conan_command, OnceArgument, conan_subcommand
from conan.cli.commands import make_abs_path
from conan.cli.args import common_graph_args
from conan.cli.printers.graph import print_graph_packages
from conans.errors import ConanException
from conans.model.graph_lock import Lockfile, LOCKFILE
from conans.model.recipe_ref import RecipeReference


@conan_command(group="Consumer")
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
    args = parser.parse_args(*args)

    # parameter validation
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None
    remotes = conan_api.remotes.list(args.remote)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, conanfile_path=path,
                                               cwd=cwd, partial=True)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    if path:
        graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                    args.user, args.channel,
                                                    profile_host, profile_build, lockfile,
                                                    remotes, args.build, args.update)
    else:
        graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                    profile_host, profile_build, lockfile,
                                                    remotes, args.build, args.update)

    conan_api.graph.analyze_binaries(graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(graph)

    lockfile = conan_api.lockfile.update_lockfile(lockfile, graph, args.lockfile_packages,
                                                  clean=args.lockfile_clean)
    conanfile_path = os.path.dirname(graph.root.path) \
        if graph.root.path and args.lockfile_out is None else cwd
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out or "conan.lock", conanfile_path)


@conan_subcommand()
def lock_merge(conan_api, parser, subparser, *args):
    """
    Merge 2 or more lockfiles
    """
    subparser.add_argument('--lockfile', action="append", help='Path to lockfile to be merged')
    subparser.add_argument("--lockfile-out", action=OnceArgument, default=LOCKFILE,
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


@conan_subcommand()
def lock_add(conan_api, parser, subparser, *args):
    """
    Add requires, build-requires or python-requires to existing or new lockfile. Resulting lockfile
    will be ordereded, newer versions/revisions first.
    References can be with our without revisions like "--requires=pkg/version", but they
    must be package references, including at least the version, they cannot contain a version range
    """
    subparser.add_argument('--requires', action="append", help='Add references to lockfile.')
    subparser.add_argument('--build-requires', action="append",
                           help='Add build-requires to lockfile')
    subparser.add_argument('--python-requires', action="append",
                           help='Add python-requires to lockfile')
    subparser.add_argument("--lockfile-out", action=OnceArgument, default=LOCKFILE,
                           help="Filename of the created lockfile")
    subparser.add_argument("--lockfile", action=OnceArgument, help="Filename of the input lockfile")
    args = parser.parse_args(*args)

    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, partial=True)

    requires = [RecipeReference.loads(r) for r in args.requires] if args.requires else None
    build_requires = [RecipeReference.loads(r) for r in args.build_requires] \
        if args.build_requires else None
    python_requires = [RecipeReference.loads(r) for r in args.python_requires] \
        if args.python_requires else None

    lockfile = conan_api.lockfile.add_lockfile(lockfile,
                                               requires=requires,
                                               python_requires=python_requires,
                                               build_requires=build_requires)
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out)
