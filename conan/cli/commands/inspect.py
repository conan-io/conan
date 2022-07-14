import json
import inspect as python_inspect

from conan.api.output import ConanOutput
from conan.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand


def _inspect_json_formatter(data):
    return json.dumps(data, indent=4)


@conan_command(group=COMMAND_GROUPS['consumer'])
def inspect(conan_api, parser, *args):
    """
    Inspect a conanfile.py to return the public fields
    """


@conan_subcommand(formatters={"json": _inspect_json_formatter})
def inspect_path(conan_api, parser, subparser, *args, **kwargs):
    """
    Returns the specified attribute/s of a conanfile
    """
    subparser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")

    args = parser.parse_args(*args)
    out = ConanOutput()
    conanfile = conan_api.graph.load_conanfile_class(args.path)
    ret = {}

    for name, value in python_inspect.getmembers(conanfile):
        if name.startswith('_') or python_inspect.ismethod(value) \
           or python_inspect.isfunction(value) or isinstance(value, property):
            continue
        ret[name] = value
        if value is None:
            continue
        if isinstance(value, dict):
            out.writeln(f"{name}:")
            for k, v in value.items():
                out.writeln(f"    {k}: {v}")
        else:
            out.writeln("{}: {}".format(name, value))

    return ret
