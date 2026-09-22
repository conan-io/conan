import os

from conan.cli.command import conan_command, OnceArgument
from conan.cli.args import add_reference_args


@conan_command(group="Creator")
def source(conan_api, parser, *args):
    """
    Call the source() method.
    """
    parser.add_argument("path", help="Path to a folder containing a conanfile.py. "
                                     "Defaults to current directory",
                        default=".", nargs="?")
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile for python-requires resolution. Use "
                             "--lockfile=\"\" to avoid automatic use of existing 'conan.lock' file")
    parser.add_argument("--lockfile-partial", action="store_true",
                        help="Do not raise an error if some dependency is not found in lockfile")
    add_reference_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    enabled_remotes = conan_api.remotes.list()  # for python_requires not local
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
    conan_api.local.source(path, name=args.name, version=args.version, user=args.user,
                           channel=args.channel, remotes=enabled_remotes, lockfile=lockfile)
