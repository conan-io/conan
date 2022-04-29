import json

from conans.cli.command import conan_command, COMMAND_GROUPS
from conans.cli.output import ConanOutput
from conans.errors import ConanException


def _inspect_json_formatter(data):
    return json.dumps(data, indent=4)


@conan_command(group=COMMAND_GROUPS['creator'], formatters={"json": _inspect_json_formatter})
def inspect(conan_api, parser, *args, **kwargs):
    """
    Returns the specified attribute/s of a conanfile
    """
    parser.add_argument("path", help="Path to a folder containing a recipe (conanfile.py)")
    parser.add_argument("attribute", help="Attribute of the conanfile to read", nargs="+")
    args = parser.parse_args(*args)
    out = ConanOutput()
    conanfile = conan_api.graph.load_conanfile_class(args.path)
    ret = {}
    for attr in args.attribute:
        try:
            value = getattr(conanfile, attr)
        except AttributeError:
            raise ConanException("The conanfile doesn't have a '{}' attribute".format(attr))
        ret[attr] = value
        out.writeln("{}: {}".format(attr, value))

    return {"attributes": ret}
