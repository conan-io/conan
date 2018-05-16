import os

from conans.util.files import rmdir, is_dirty
from conans.model.ref import PackageReference
from conans.client.output import ScopedOutput
from conans.errors import NotFoundException, NoRemoteAvailable
from conans.model.manifest import FileTreeManifest
from conans.model.info import ConanInfo
from conans.paths import CONANINFO


class GraphBinariesAnalyzer(object):
    def __init__(self, client_cache, output, remote_manager, registry):
        self._client_cache = client_cache
        self._out = output
        self._remote_manager = remote_manager
        self._registry = registry

    def _get_remote(self, conan_ref, remote_name):
        if remote_name:
            return self._registry.remote(remote_name)
        remote = self._registry.get_ref(conan_ref)
        if remote:
            return remote

        try:
            return self._registry.default_remote
        except NoRemoteAvailable:
            return None

    def _get_package_info(self, package_ref, remote):
        try:
            remote_info = self._remote_manager.get_package_info(package_ref, remote)
            return remote_info
        except (NotFoundException, NoRemoteAvailable):  # 404 or no remote
            return False

    def _check_update(self, package_folder, package_ref, remote, output):
        try:  # get_conan_digest can fail, not in server
            # FIXME: This can iterate remotes to get and associate in registry
            upstream_manifest = self._remote_manager.get_package_manifest(package_ref, remote)
        except NotFoundException:
            output.warn("Can't update, no package in remote")
        except NoRemoteAvailable:
            output.warn("Can't update, no remote defined")
        else:
            read_manifest = FileTreeManifest.load(package_folder)
            if upstream_manifest != read_manifest:
                if upstream_manifest.time > read_manifest.time:
                    output.warn("Current package is older than remote upstream one")
                    return True
                else:
                    output.warn("Current package is newer than remote upstream one")

    def _evaluate_node(self, node, build_mode, update, remote_name, evaluated_references):
        assert node.binary is None

        conan_ref, conanfile = node.conan_ref, node.conanfile
        package_id = conanfile.info.package_id()
        package_ref = PackageReference(conan_ref, package_id)
        # Check that this same reference hasn't already been checked
        previous_node = evaluated_references.get(package_ref)
        if previous_node:
            node.binary = previous_node.binary
            node.remote = previous_node.remote
            return
        evaluated_references[package_ref] = node

        output = ScopedOutput(str(conan_ref), self._out)
        if build_mode.forced(conanfile, conan_ref):
            output.warn('Forced build from source')
            node.binary = "BUILD"
            return

        package_folder = self._client_cache.package(package_ref,
                                                    short_paths=conanfile.short_paths)

        # Check if dirty, to remove it
        with self._client_cache.package_lock(package_ref):
            if is_dirty(package_folder):
                output.warn("Package is corrupted, removing folder: %s" % package_folder)
                rmdir(package_folder)

        if os.path.exists(package_folder):
            if update:
                remote = self._get_remote(conan_ref, remote_name)
                if remote:
                    if self._check_update(package_folder, package_ref, remote, output):
                        node.binary = "UPDATE"
                        node.remote = remote
                        if build_mode.outdated:
                            package_hash = self._get_package_info(package_ref, remote).recipe_hash
                else:
                    output.warn("Can't update, no remote defined")
            if not node.binary:
                node.binary = "INSTALLED"
                package_hash = ConanInfo.load_file(os.path.join(package_folder, CONANINFO)).recipe_hash
        else:  # Binary does NOT exist locally
            remote = self._get_remote(conan_ref, remote_name)
            remote_info = None
            if remote:
                remote_info = self._get_package_info(package_ref, remote)
            if remote_info:
                node.binary = "DOWNLOAD"
                node.remote = remote
                package_hash = remote_info.recipe_hash
            else:
                if build_mode.allowed(conanfile):
                    node.binary = "BUILD"
                else:
                    node.binary = "MISSING"

        if build_mode.outdated:
            if node.binary == "MISSING":
                node.binary = "BUILD"
            elif node.binary in ("INSTALLED", "DOWNLOAD", "UPDATE"):
                local_recipe_hash = self._client_cache.load_manifest(package_ref.conan).summary_hash
                if local_recipe_hash != package_hash:
                    output.info("Outdated package!")
                    node.binary = "BUILD"
                else:
                    output.info("Package is up to date")

    def evaluate_graph(self, deps_graph, build_mode, update, remote_name):

        evaluated_references = {}
        for node in deps_graph.nodes:
            conan_ref, conanfile = node.conan_ref, node.conanfile
            if not conan_ref:
                continue

            if [r for r in conanfile.requires.values() if r.private]:
                self._evaluate_node(node, build_mode, update, remote_name, evaluated_references)
                if node.binary != "BUILD":
                    closure = deps_graph.closure(node, private=True)
                    for node in closure.values():
                        node.binary = "SKIP"

        for node in deps_graph.nodes:
            conan_ref, conanfile = node.conan_ref, node.conanfile
            if not conan_ref or node.binary:
                continue
            self._evaluate_node(node, build_mode, update, remote_name, evaluated_references)
