import json

from conans.cli.command import conan_command, Extender, OnceArgument


def output_create_cli(info, out):
    full_reference = info["full_reference"]
    out.write(full_reference)


def output_create_json(info, out):
    myjson = json.dumps(info, indent=4)
    out.write(myjson)


@conan_command(group="Creator commands", formatters={"cli": output_create_cli,
                                                     "json": output_create_json})
def create(conan_api, parser, *args, **kwargs):
    """
    Builds a binary package for a recipe (conanfile.py).

    Uses the specified configuration in a profile or in -s settings, -o
    options, etc. If a 'test_package' folder (the name can be configured
    with -tf) is found, the command will run the consumer project to ensure
    that the package has been created correctly. Check 'conan test' command
    to know more about 'test_folder' project.
    """

    parser.add_argument("conanfile", help="Path to the conanfile.py e.g., my_folder/conanfile.py")
    parser.add_argument("--name", default=None, action=OnceArgument,
                        help="Package name. If name is declared in conanfile, they should match")
    parser.add_argument("--version", default=None, action=OnceArgument,
                        help="Package version. If version is declared in conanfile, they should match")
    parser.add_argument("--user", default=None, action=OnceArgument,
                        help="Package user. If user is declared in conanfile, they should match")
    parser.add_argument("--channel", default=None, action=OnceArgument,
                        help="Package channel. If channel is declared in conanfile, they should match")
    args = parser.parse_args(*args)
    info = conan_api.create(args.conanfile, args.name, args.version, args.user, args.channel)
    return info
