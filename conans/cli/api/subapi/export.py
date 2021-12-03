from conans.cli.api.subapi import api_method
from conans.cli.commands.install import _get_conanfile_path
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.cmd.export import cmd_export
from conans.client.cmd.export_pkg import export_pkg
from conans.client.conan_api import _make_abs_path
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.errors import ConanException


class ExportAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def export(self, path, name, version, user, channel,
               lockfile=None, ignore_dirty=False):
        app = ConanApp(self.conan_api.cache_folder)
        cmd_export(app, path, name, version, user, channel,
                   graph_lock=lockfile, ignore_dirty=ignore_dirty)

    @api_method
    def export_pkg(self, conanfile_path, name, version=None, user=None, channel=None,
                   profile_host=None, profile_build=None, force=False,
                   cwd=None, lockfile=None, ignore_dirty=False):
        app = ConanApp(self.conan_api.cache_folder)
        new_ref = cmd_export(app, conanfile_path, name, version, user, channel,
                             graph_lock=lockfile, ignore_dirty=ignore_dirty)
        # new_ref has revision
        export_pkg(app, new_ref,
                   profile_host=profile_host, profile_build=profile_build,
                   graph_lock=lockfile, force=force,
                   source_conanfile_path=conanfile_path)


