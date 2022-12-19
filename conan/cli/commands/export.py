import json
import os

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.cli.args import add_reference_args


def common_args_export(parser):
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    add_reference_args(parser)


def json_export(ref):
    cli_out_write(json.dumps({"reference": ref.repr_notime()}))


@conan_command(group="Creator", formatters={"json": json_export})
def export(conan_api, parser, *args):
    """
    Export recipe to the Conan package cache
    """
    common_args_export(parser)
    parser.add_argument("-r", "--remote", action="append", default=None,
                        help='Look in the specified remote or remotes server')
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile.")
    parser.add_argument("--lockfile-out", action=OnceArgument,
                        help="Filename of the updated lockfile")
    parser.add_argument("--lockfile-partial", action="store_true",
                        help="Do not raise an error if some dependency is not found in lockfile")
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='The provided reference is a build-require')
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    remotes = conan_api.remotes.list(args.remote)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial)
    ref, conanfile = conan_api.export.export(path=path,
                                             name=args.name, version=args.version,
                                             user=args.user, channel=args.channel,
                                             lockfile=lockfile,
                                             remotes=remotes)
    lockfile = conan_api.lockfile.update_lockfile_export(lockfile, conanfile, ref,
                                                         args.build_require)
    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
    ConanOutput().success("Exported recipe: {}".format(ref.repr_humantime()))
    return ref
