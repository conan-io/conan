import os

from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.cmd.export import cmd_export
from conans.client.conanfile.package import run_package_method
from conans.client.graph.graph import BINARY_INVALID
from conans.errors import ConanInvalidConfiguration
from conans.model.package_ref import PkgReference


class ExportAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def export(self, path, name, version, user, channel, lockfile=None):
        app = ConanApp(self.conan_api.cache_folder)
        return cmd_export(app, path, name, version, user, channel, graph_lock=lockfile)

    @api_method
    def export_pkg(self, deps_graph, path):
        app = ConanApp(self.conan_api.cache_folder)
        cache, hook_manager = app.cache, app.hook_manager

        # The graph has to be loaded with build_mode=[ref.name], so that node is not tried
        # to be downloaded from remotes
        # passing here the create_reference=ref argument is useful so the recipe is in "develop",
        # because the "package()" method is in develop=True already

        # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
        # which is the exported pkg
        # TODO: Seems this could be changed, loading conanfile from cache, but locally setting
        #   to local folder?
        nodes = deps_graph.root.neighbors()
        pkg_node = nodes[0]
        ref = pkg_node.ref
        if pkg_node.binary == BINARY_INVALID:
            binary, reason = pkg_node.conanfile.info.invalid
            msg = "{}: Invalid ID: {}: {}".format(ref, binary, reason)
            raise ConanInvalidConfiguration(msg)
        conanfile = pkg_node.conanfile

        package_id = pkg_node.package_id
        assert package_id is not None
        ConanOutput().info("Packaging to %s" % package_id)
        pref = PkgReference(ref, package_id)
        pkg_layout = cache.create_build_pkg_layout(pref)

        dest_package_folder = pkg_layout.package()

        conanfile_folder = os.path.dirname(path)
        conanfile.folders.set_base_build(conanfile_folder)
        conanfile.folders.set_base_source(conanfile_folder)
        conanfile.folders.set_base_package(dest_package_folder)
        conanfile.folders.set_base_generators(conanfile_folder)

        with pkg_layout.set_dirty_context_manager():
            conan_file_path = cache.ref_layout(ref).conanfile()
            prev = run_package_method(conanfile, package_id, hook_manager, conan_file_path, ref)

        pref = PkgReference(pref.ref, pref.package_id, prev)
        pkg_layout.reference = pref
        cache.assign_prev(pkg_layout)
        # Make sure folder is updated
        conanfile.folders.set_base_package(pkg_layout.package())
