import json
import inspect as python_inspect
import sys

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand
from conan.cli.commands import default_json_formatter


def inspect_text_formatter(data):
    for name, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            cli_out_write(f"{name}:")
            for k, v in value.items():
                cli_out_write(f"    {k}: {v}")
        else:
            cli_out_write("{}: {}".format(name, value))


@conan_command(group=COMMAND_GROUPS['consumer'])
def inspect(conan_api, parser, *args):
    """
    Inspect a conanfile.py to return the public fields
    """


@conan_subcommand(formatters={"text": inspect_text_formatter, "json": default_json_formatter})
def inspect_path(conan_api, parser, subparser, *args, **kwargs):
    """
    Returns the specified attribute/s of a conanfile
    """
    subparser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")

    args = parser.parse_args(*args)
    conanfile = conan_api.graph.load_conanfile_class(args.path)
    ret = {}

    for name, value in python_inspect.getmembers(conanfile):
        if name.startswith('_') or python_inspect.ismethod(value) \
           or python_inspect.isfunction(value) or isinstance(value, property):
            continue
        ret[name] = value
        if value is None:
            continue

    return ret
