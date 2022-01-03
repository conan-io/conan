import os

from conans.cli.command import conan_command, COMMAND_GROUPS
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import save


@conan_command(group=COMMAND_GROUPS['creator'])
def new(conan_api, parser, *args):
    """
    Create a new recipe (with conanfile.py and other files) from a predefined template
    """
    parser.add_argument("template", help="Template name, predefined one or user one")
    parser.add_argument("-f", "--force", action='store_true', help="Overwrite file if exists")

    args, unknown = parser.parse_known_args(*args)
    # Manually parsing the remainder
    definitions = {}
    for u in unknown:
        k, v = u.split("=", 1)
        k = k.replace("-", "")  # Remove possible "--name=value"
        definitions[k] = v

    files = conan_api.new.new(args.template, definitions)

    # Saving the resulting files
    cwd = os.getcwd()
    # Making sure they don't overwrite existing files
    for f, v in sorted(files.items()):
        path = os.path.join(cwd, f)
        if os.path.exists(path) and not args.force:
            raise ConanException(f"File '{f}' already exists, and --force not defined, aborting")
    # And respecting binary/text encodings
    for f, v in sorted(files.items()):
        path = os.path.join(cwd, f)
        if isinstance(v, str):
            save(path, v)
        else:
            open(path, "wb").write(v)
        ConanOutput().success("File saved: %s" % f)
