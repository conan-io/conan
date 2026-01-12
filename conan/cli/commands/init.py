import os

from conan.cli.command import conan_command


@conan_command(group="Creator")
def init(conan_api, parser, *args):
    """
    Creates a quite basic conanfile.py file.
    """
    parser.add_argument("path", nargs="?", help="Path to save the conanfile.py file. "
                                     "Default: current working directory", default=os.getcwd())
    parser.add_argument("-r", "--ref", help="Recipe reference. Default: 'hello/1.0'",
                        default="hello/1.0")
    args = parser.parse_args(*args)
    conan_api.init.save_conanfile(args.path, args.ref)
