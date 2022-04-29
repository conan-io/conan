import os

from conans.cli.command import conan_command, COMMAND_GROUPS
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import get_lockfile, add_lockfile_args, add_reference_args
from conans.model.graph_lock import Lockfile


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
    lockfile = get_lockfile(lockfile_path=args.lockfile, cwd=cwd, strict=not args.lockfile_no_strict)
    path = _get_conanfile_path(args.path, cwd, py=None) if args.path else None
    ref = conan_api.export.export(path=path,
                                  name=args.name, version=args.version,
                                  user=args.user, channel=args.channel,
                                  lockfile=lockfile)

    if args.lockfile_out:
        if lockfile is None:
            lockfile = Lockfile()
            lockfile.update_lock_export_ref(ref)
        # It was updated inside ``export()`` api
        lockfile_out = make_abs_path(args.lockfile_out, cwd)
        lockfile.save(lockfile_out)
