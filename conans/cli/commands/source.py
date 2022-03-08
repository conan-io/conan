import os

from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.common import add_reference_args
from conans.cli.conan_app import ConanApp
from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import CONTEXT_HOST
from conans.client.graph.profile_node_definer import initialize_conanfile_profile
from conans.client.source import run_source_method
from conans.errors import conanfile_exception_formatter
from conans.model.options import Options


@conan_command(group=COMMAND_GROUPS['creator'])
def source(conan_api, parser, *args):
    """
    Install + calls the build() method
    """
    parser.add_argument("path", nargs="?",
                        help="Path to a folder containing a recipe (conanfile.py "
                             "or conanfile.txt) or to a recipe file. e.g., "
                             "./my_project/conanfile.txt.")
    add_reference_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = _get_conanfile_path(args.path, cwd, py=True)
    folder = os.path.dirname(path)

    # TODO: Decide API to put this
    app = ConanApp(conan_api.cache_folder)
    profile_host = conan_api.profiles.get_profile([conan_api.profiles.get_default_host()])

    profile_host.conf.rebase_conf_definition(app.cache.new_config)
    conanfile = app.loader.load_consumer(path,
                                         name=args.name, version=args.version,
                                         user=args.user, channel=args.channel,
                                         graph_lock=None)

    initialize_conanfile_profile(conanfile, profile_host, profile_host, CONTEXT_HOST, False)
    run_configure_method(conanfile, down_options=Options(),
                         profile_options=profile_host.options, ref=None)

    # This is important, otherwise the ``conan source`` doesn't define layout and fails
    if hasattr(conanfile, "layout"):
        with conanfile_exception_formatter(conanfile, "layout"):
            conanfile.layout()

    conanfile.folders.set_base_source(folder)
    conanfile.folders.set_base_build(None)
    conanfile.folders.set_base_package(None)

    run_source_method(conanfile, app.hook_manager, coanfile_path=path)
