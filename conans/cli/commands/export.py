import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile, add_lockfile_args, add_reference_args


def common_args_export(parser):
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    add_reference_args(parser)


@conan_command(group=COMMAND_GROUPS['creator'])
def export(conan_api, parser, *args, **kwargs):
    """
    Export recipe to the Conan package cache
    """
    common_args_export(parser)
    add_lockfile_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    lockfile_path = make_abs_path(args.lockfile, cwd)
    lockfile = get_lockfile(lockfile=lockfile_path, strict=args.lockfile_strict)
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None

    conan_api.export.export(path=path,
                            name=args.name, version=args.version,
                            user=args.user, channel=args.channel,
                            lockfile=lockfile)

    if args.lockfile_out:
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        lockfile.save(lockfile_out)
