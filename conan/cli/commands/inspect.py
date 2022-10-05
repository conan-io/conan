import json
import inspect as python_inspect
import sys

from conan.api.output import ConanOutput
from conan.cli.command import conan_command, COMMAND_GROUPS
from conan.cli.commands import default_json_formatter


def inspect_text_formatter(data):
    out = ConanOutput(stream=sys.stdout)
    for name, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            out.writeln(f"{name}:")
            for k, v in value.items():
                out.writeln(f"    {k}: {v}")
        else:
            out.writeln("{}: {}".format(name, value))


@conan_command(group=COMMAND_GROUPS['consumer'], formatters={"text": inspect_text_formatter, "json": default_json_formatter})
def inspect(conan_api, parser, *args):
    """
    Inspect a conanfile.py to return the public fields
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")

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
