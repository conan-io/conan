import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile


def common_args_export(parser):
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")

    parser.add_argument("--name", action=OnceArgument,
                        help='Provide a package name if not specified in conanfile')
    parser.add_argument("--version", action=OnceArgument,
                        help='Provide a package version if not specified in conanfile')
    parser.add_argument("--user", action=OnceArgument,
                        help='Provide a user')
    parser.add_argument("--channel", action=OnceArgument,
                        help='Provide a channel')
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile file.")
    parser.add_argument("--lockfile-out", action=OnceArgument,
                        help="Filename of the updated lockfile")
    parser.add_argument("--lockfile-strict", action="store_true",
                        help="Raise an error if some dependency is not found in lockfile")
    parser.add_argument("--ignore-dirty", default=False, action='store_true',
                        help='When using the "scm" feature with "auto" values, capture the'
                             ' revision and url even if there are uncommitted changes')


@conan_command(group=COMMAND_GROUPS['creator'])
def export(conan_api, parser, *args, **kwargs):
    """
    Export recipe to the Conan package cache
    """
    common_args_export(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    lockfile_path = make_abs_path(args.lockfile, cwd)
    lockfile = get_lockfile(lockfile=lockfile_path, strict=args.lockfile_strict)
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None

    conan_api.export.export(path=path,
                            name=args.name, version=args.version,
                            user=args.user, channel=args.channel,
                            lockfile=lockfile,
                            ignore_dirty=args.ignore_dirty)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        lockfile.save(lockfile_out)
