import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands import make_abs_path
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.conan_app import ConanApp
from conans.client.source import config_source_local


@conan_command(group=COMMAND_GROUPS['creator'])
def source(conan_api, parser, *args):
    """
    Install + calls the build() method
    """
    parser.add_argument("path", nargs="?",
                        help="Path to a folder containing a recipe (conanfile.py "
                             "or conanfile.txt) or to a recipe file. e.g., "
                             "./my_project/conanfile.txt.")
    parser.add_argument("--name", action=OnceArgument,
                        help='Provide a package name if not specified in conanfile')
    parser.add_argument("--version", action=OnceArgument,
                        help='Provide a package version if not specified in conanfile')
    parser.add_argument("--user", action=OnceArgument, help='Provide a user')
    parser.add_argument("--channel", action=OnceArgument, help='Provide a channel')
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = _get_conanfile_path(args.path, cwd, py=True)
    folder = os.path.dirname(path)

    # TODO: Decide API to put this
    app = ConanApp(conan_api.cache_folder)
    conanfile = app.graph_manager.load_consumer_conanfile(path, name=args.name, version=args.version,
                                                          user=args.user, channel=args.channel)
    conanfile.folders.set_base_source(folder)
    conanfile.folders.set_base_build(None)
    conanfile.folders.set_base_package(None)

    config_source_local(conanfile, cwd, app.hook_manager)
