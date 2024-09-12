import os
import shutil

from jinja2 import Environment, meta, exceptions

from conan.api.output import ConanOutput
from conan.cli.command import conan_command
from conan.errors import ConanException
from conans.util.files import save


@conan_command(group="Creator")
def new(conan_api, parser, *args):
    """
    Create a new example recipe and source files from a template.
    """
    parser.add_argument("template", help="Template name, "
                        "either a predefined built-in or a user-provided one. "
                        "Available built-in templates: basic, cmake_lib, cmake_exe, "
                        "meson_lib, meson_exe, msbuild_lib, msbuild_exe, bazel_lib, bazel_exe, "
                        "autotools_lib, autotools_exe, local_recipes_index. "
                        "E.g. 'conan new cmake_lib -d name=hello -d version=0.1'. "
                        "You can define your own templates too by inputting an absolute path "
                        "as your template, or a path relative to your conan home folder."
                        )
    parser.add_argument("-d", "--define", action="append",
                        help="Define a template argument as key=value, e.g., -d name=mypkg")
    parser.add_argument("-f", "--force", action='store_true', help="Overwrite file if it already exists")

    args = parser.parse_args(*args)
    # Manually parsing the remainder
    definitions = {}
    for u in args.define or []:
        try:
            k, v = u.split("=", 1)
        except ValueError:
            raise ConanException(f"Template definitions must be 'key=value', received {u}")
        k = k.replace("-", "")  # Remove possible "--name=value"
        # For variables that only show up once, no need for list to keep compatible behaviour
        if k in definitions:
            if isinstance(definitions[k], list):
                definitions[k].append(v)
            else:
                definitions[k] = [definitions[k], v]
        else:
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

    try:
        template_files = conan_api.new.render(template_files, definitions)
    except exceptions.UndefinedError:
        def get_template_vars():
            template_vars = []
            for _, templ_str in template_files.items():
                env = Environment()
                ast = env.parse(templ_str)
                template_vars.extend(meta.find_undeclared_variables(ast))

            injected_vars = {"conan_version", "package_name", "as_name"}
            optional_vars = {"requires", "tool_requires", "output_root_dir"}
            template_vars = list(set(template_vars) - injected_vars - optional_vars)
            template_vars.sort()
            return template_vars

        raise ConanException("Missing definitions for the template. "
                             "Required definitions are: {}"
                             .format(", ".join("'{}'".format(var) for var in get_template_vars())))

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
