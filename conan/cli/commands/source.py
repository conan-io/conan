import os

from conan.cli.command import conan_command
from conan.cli.args import add_reference_args
from conan.internal.conan_app import ConanApp
from conans.client.graph.graph import CONTEXT_HOST
from conans.client.graph.profile_node_definer import initialize_conanfile_profile
from conans.client.source import run_source_method
from conans.errors import conanfile_exception_formatter


@conan_command(group="Creator")
def source(conan_api, parser, *args):
    """
    Calls the source() method
    """
    parser.add_argument("path", nargs="?",
                        help="Path to a folder containing a recipe (conanfile.py "
                             "or conanfile.txt) or to a recipe file. e.g., "
                             "./my_project/conanfile.txt.")
    add_reference_args(parser)
    args = parser.parse_args(*args)

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    folder = os.path.dirname(path)

    # TODO: Decide API to put this
    app = ConanApp(conan_api.cache_folder)
    # This profile is empty, but with the conf from global.conf
    profile = conan_api.profiles.get_profile([])
    conanfile = app.loader.load_consumer(path,
                                         name=args.name, version=args.version,
                                         user=args.user, channel=args.channel,
                                         graph_lock=None)

    initialize_conanfile_profile(conanfile, profile, profile, CONTEXT_HOST, False)
    # This is important, otherwise the ``conan source`` doesn't define layout and fails
    if hasattr(conanfile, "layout"):
        with conanfile_exception_formatter(conanfile, "layout"):
            conanfile.layout()

    conanfile.folders.set_base_source(folder)
    conanfile.folders.set_base_export_sources(folder)
    conanfile.folders.set_base_build(None)
    conanfile.folders.set_base_package(None)

    run_source_method(conanfile, app.hook_manager)
