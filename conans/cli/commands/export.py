import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile, add_reference_args
from conans.cli.output import ConanOutput


def common_args_export(parser):
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    add_reference_args(parser)


@conan_command(group=COMMAND_GROUPS['creator'])
def export(conan_api, parser, *args):
    """
    Export recipe to the Conan package cache
    """
    common_args_export(parser)
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile.")
    parser.add_argument("--lockfile-no-strict", action="store_true",
                        help="Raise an error if some dependency is not found in lockfile")

    args = parser.parse_args(*args)

    cwd = os.getcwd()
    lockfile = get_lockfile(lockfile_path=args.lockfile, cwd=cwd, strict=not args.lockfile_no_strict)
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None
    ref = conan_api.export.export(path=path,
                                  name=args.name, version=args.version,
                                  user=args.user, channel=args.channel,
                                  lockfile=lockfile)
    ConanOutput().success("Exported recipe: {}".format(ref.repr_humantime()))
