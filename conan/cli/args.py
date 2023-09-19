import argparse

from conan.cli.command import OnceArgument
from conan.errors import ConanException

_help_build_policies = '''Optional, specify which packages to build from source. Combining multiple
    '--build' options on one command line is allowed.
    Possible values:

    --build="*"        Force build from source for all packages.
    --build=never      Disallow build for all packages, use binary packages or fail if a binary
                       package is not found, it cannot be combined with other '--build' options.
    --build=missing    Build packages from source whose binary package is not found.
    --build=cascade    Build packages from source that have at least one dependency being built from
                       source.
    --build=[pattern]  Build packages from source whose package reference matches the pattern. The
                       pattern uses 'fnmatch' style wildcards.
    --build=~[pattern] Excluded packages, which will not be built from the source, whose package
                       reference matches the pattern. The pattern uses 'fnmatch' style wildcards.
    --build=missing:[pattern] Build from source if a compatible binary does not exist, only for
                              packages matching pattern.
'''


def add_lockfile_args(parser):
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile. Use --lockfile=\"\" to avoid automatic use of "
                             "existing 'conan.lock' file")
    parser.add_argument("--lockfile-partial", action="store_true",
                        help="Do not raise an error if some dependency is not found in lockfile")
    parser.add_argument("--lockfile-out", action=OnceArgument,
                        help="Filename of the updated lockfile")
    parser.add_argument("--lockfile-packages", action="store_true",
                        help="Lock package-id and package-revision information")
    parser.add_argument("--lockfile-clean", action="store_true",
                        help="Remove unused entries from the lockfile")
    parser.add_argument("--lockfile-overrides",
                        help="Overwrite lockfile overrides")


def add_common_install_arguments(parser):
    parser.add_argument("-b", "--build", action="append", help=_help_build_policies)

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')

    update_help = ("Will check the remote and in case a newer version and/or revision of "
                   "the dependencies exists there, it will install those in the local cache. "
                   "When using version ranges, it will install the latest version that "
                   "satisfies the range. Also, if using revisions, it will update to the "
                   "latest revision for the resolved version range.")
    parser.add_argument("-u", "--update", action='store_true', default=False,
                        help=update_help)
    add_profiles_args(parser)


def add_profiles_args(parser):
    class ContextAllAction(argparse.Action):
        def __init__(self,
                     option_strings,
                     dest,
                     nargs=None,
                     const=None,
                     default=None,
                     type=None,
                     choices=None,
                     required=False,
                     help=None,
                     metavar=None,
                     contexts=None):
            if nargs == 0:
                raise ValueError('nargs for append actions must be != 0; if arg '
                                 'strings are not supplying the value to append, '
                                 'the append const action may be more appropriate')
            if const is not None and nargs != argparse.OPTIONAL:
                raise ValueError('nargs must be %r to supply const' % argparse.OPTIONAL)
            super(ContextAllAction, self).__init__(
                option_strings=option_strings,
                dest=dest,
                nargs=nargs,
                const=const,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar)
            self.contexts = contexts

        def __call__(self, action_parser, namespace, values, option_string=None):
            for context in self.contexts:
                items = getattr(namespace, self.dest + "_" + context, None)
                items = items[:] if items else []
                items.append(values)
                setattr(namespace, self.dest + "_" + context, items)

    def create_config(short, long, example=None):
        parser.add_argument(f"-{short}", f"--{long}",
                            default=None,
                            action="append",
                            dest=f"{long}_host",
                            metavar=long.upper(),
                            help='Apply the specified profile. '
                                 f'By default, or if specifying -{short}:h (--{long}:host), it applies to the host context. '
                                 f'Use -{short}:b (--{long}:build) to specify the build context, '
                                 f'or -{short}:a (--{long}:all) to specify both contexts at once'
                                  + ('' if not example else f". Example: {example}"))
        contexts = ["build", "host"]
        for context in contexts:
            parser.add_argument(f"-{short}:{context[0]}", f"--{short}:{context}",
                                default=None,
                                action="append",
                                dest=f"{long}_{context}",
                                help="")

        parser.add_argument(f"-{short}:a", f"--{long}:all",
                            default=None,
                            action=ContextAllAction,
                            dest=long,
                            metavar=f"{long.upper()}_ALL",
                            help="",
                            contexts=contexts)

    create_config("pr", "profile")
    create_config("o", "options", "-o pkg:with_qt=true")
    create_config("s", "settings", "-s compiler=gcc")
    create_config("c", "conf", "-c tools.cmake.cmaketoolchain:generator=Xcode")


def add_reference_args(parser):
    parser.add_argument("--name", action=OnceArgument,
                        help='Provide a package name if not specified in conanfile')
    parser.add_argument("--version", action=OnceArgument,
                        help='Provide a package version if not specified in conanfile')
    parser.add_argument("--user", action=OnceArgument,
                        help='Provide a user if not specified in conanfile')
    parser.add_argument("--channel", action=OnceArgument,
                        help='Provide a channel if not specified in conanfile')


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
    add_common_install_arguments(subparser)
    add_lockfile_args(subparser)


def validate_common_graph_args(args):
    if args.requires and (args.name or args.version or args.user or args.channel):
        raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                             "--requires")
    if args.channel and not args.user:
        raise ConanException("Can't specify --channel without --user")
    if not args.path and not args.requires and not args.tool_requires:
        raise ConanException("Please specify a path to a conanfile or a '--requires=<ref>'")
    if args.path and (args.requires or args.tool_requires):
        raise ConanException("--requires and --tool-requires arguments are incompatible with "
                             f"[path] '{args.path}' argument")
    if not args.path and args.build_require:
        raise ConanException("--build-require should only be used with <path> argument")
