import os

from conan.api.output import cli_out_write
from conan.cli.command import conan_command, OnceArgument
from conan.cli.formatters import default_json_formatter


def inspect_text_formatter(data):
    for name, value in sorted(data.items()):
        if value is None:
            continue
        if isinstance(value, dict):
            cli_out_write(f"{name}:")
            for k, v in value.items():
                cli_out_write(f"    {k}: {v}")
        else:
            cli_out_write("{}: {}".format(name, str(value)))


@conan_command(group="Consumer", formatters={"text": inspect_text_formatter, "json": default_json_formatter})
def inspect(conan_api, parser, *args):
    """
    Inspect a conanfile.py to return its public fields.
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    parser.add_argument("-r", "--remote", default=None, action="append",
                        help="Remote names. Accepts wildcards ('*' means all the remotes available)")
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile. Use --lockfile=\"\" to avoid automatic use of "
                             "existing 'conan.lock' file")
    parser.add_argument("--lockfile-partial", action="store_true",
                        help="Do not raise an error if some dependency is not found in lockfile")

    args = parser.parse_args(*args)
    path = conan_api.local.get_conanfile_path(args.path, os.getcwd(), py=True)
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=os.getcwd(),
                                               partial=args.lockfile_partial)
    remotes = conan_api.remotes.list(args.remote) if args.remote else []
    conanfile = conan_api.local.inspect(path, remotes=remotes, lockfile=lockfile)
    result = conanfile.serialize()
    # Some of the serialization info is not initialized so it's pointless to show it to the user
    for item in ("cpp_info", "system_requires", "recipe_folder"):
        if item in result:
            del result[item]

    return result
