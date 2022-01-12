import os
import shutil

from conans.cli.command import conan_command, COMMAND_GROUPS, Extender
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import save


@conan_command(group=COMMAND_GROUPS['creator'])
def new(conan_api, parser, *args):
    """
    Create a new recipe (with conanfile.py and other files) from a predefined template
    """
    parser.add_argument("template", help="Template name, built-in predefined one or user one")
    parser.add_argument("-d", "--define", action=Extender,
                        help="Define a template argument as key=value")
    parser.add_argument("-f", "--force", action='store_true', help="Overwrite file if exists")

    args = parser.parse_args(*args)
    # Manually parsing the remainder
    definitions = {}
    for u in args.define or []:
        try:
            k, v = u.split("=", 1)
        except ValueError:
            raise ConanException(f"Template definitions must be 'key=value', received {u}")
        k = k.replace("-", "")  # Remove possible "--name=value"
        definitions[k] = v

    files = conan_api.new.get_template(args.template)  # First priority: user folder
    if not files:  # then, try the templates in the Conan home
        files = conan_api.new.get_home_template(args.template)
    if files:
        template_files, non_template_files = files
    else:
        template_files = conan_api.new.get_builtin_template(args.template)
        non_template_files = {}

    if not template_files and not non_template_files:
        raise ConanException("Template doesn't exist or not a folder: {}".format(args.template))

    template_files = conan_api.new.render(template_files, definitions)

    # Saving the resulting files
    output = ConanOutput()
    cwd = os.getcwd()
    # Making sure they don't overwrite existing files
    for f, v in sorted(template_files.items()):
        path = os.path.join(cwd, f)
        if os.path.exists(path) and not args.force:
            raise ConanException(f"File '{f}' already exists, and --force not defined, aborting")
        save(path, v)
        output.success("File saved: %s" % f)

    # copy non-templates
    for f, v in sorted(non_template_files.items()):
        path = os.path.join(cwd, f)
        if os.path.exists(path) and not args.force:
            raise ConanException(f"File '{f}' already exists, and --force not defined, aborting")
        shutil.copy2(v, path)
        output.success("File saved: %s" % f)
