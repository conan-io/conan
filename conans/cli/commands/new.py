import argparse
import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.output import ConanOutput
from conans.util.files import save_files


@conan_command(group=COMMAND_GROUPS['creator'])
def new(conan_api, parser, *args):
    """
    Create a new conanfile.py from a predefined templated
    """
    parser.add_argument("template", help="Template name, predefined one or user one")
    parser.add_argument("remainder", nargs=argparse.REMAINDER)

    args = parser.parse_args(*args)

    # Manually parsing the remainder
    definitions = {}
    for u in args.remainder:
        k, v = u.split("=", 1)
        k = k.replace("-", "")  # Remove possible "--name=value"
        definitions[k] = v
    files = conan_api.new.new(args.template, definitions)
    print(files)
    cwd = os.getcwd()
    save_files(cwd, files)
    for f in sorted(files):
        ConanOutput().success("File saved: %s" % f)

