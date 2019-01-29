import os

from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_SKIP, BINARY_UPDATE, BINARY_WORKSPACE,
                                       RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL)
from conans.errors import NoRemoteAvailable, NotFoundException
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.util.env_reader import get_env
from conans.util.files import is_dirty, rmdir


class GraphBinariesAnalyzer(object):
    def __init__(self, cache, output, remote_manager, workspace):
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager
        self._registry = cache.registry
        self._workspace = workspace

    def _get_package_info(self, pref, remote):
        try:
            remote_info = self._remote_manager.get_package_info(pref, remote)
            return remote_info
        except (NotFoundException, NoRemoteAvailable):  # 404 or no remote
            return False

    def _check_update(self, package_folder, pref, remote, output, node):

        revisions_enabled = get_env("CONAN_CLIENT_REVISIONS_ENABLED", False)
        if revisions_enabled:
            metadata = self._cache.package_layout(pref.ref).load_metadata()
            rec_rev = metadata.packages[pref.id].recipe_revision
            if rec_rev != node.ref.revision:
                output.warn("Outdated package! The package doesn't belong "
                            "to the installed recipe revision: %s" % str(pref))

        try:  # get_conan_digest can fail, not in server
            # FIXME: This can iterate remotes to get and associate in registry
            if not revisions_enabled and not node.revision_pinned:
                # Compatibility mode and user hasn't specified the revision, so unlock
                # it to find any binary for any revision
                pref = pref.copy_clear_rev()

            upstream_manifest = self._remote_manager.get_package_manifest(pref, remote)
        except NotFoundException:
            output.warn("Can't update, no package in remote")
        except NoRemoteAvailable:
            output.warn("Can't update, no remote defined")
        else:
            read_manifest = FileTreeManifest.load(package_folder)
            if upstream_manifest != read_manifest:
                if upstream_manifest.time > read_manifest.time:
                    output.warn("Current package is older than remote upstream one")
                    node.update_manifest = upstream_manifest
                    return True
                else:
                    output.warn("Current package is newer than remote upstream one")

    def _evaluate_node(self, node, build_mode, update, evaluated_nodes, remote_name):
        assert node.binary is None

        ref, conanfile = node.ref, node.conanfile
        revisions_enabled = get_env("CONAN_CLIENT_REVISIONS_ENABLED", False)
        package_id = conanfile.info.package_id()
        pref = PackageReference(ref, package_id)
        # Check that this same reference hasn't already been checked
        previous_node = evaluated_nodes.get(pref)
        if previous_node:
            node.binary = previous_node.binary
            node.binary_remote = previous_node.binary_remote
            return
        evaluated_nodes[pref] = node

        output = conanfile.output

        if node.recipe == RECIPE_EDITABLE:
            node.binary = BINARY_EDITABLE
            return

        if build_mode.forced(conanfile, ref):
            output.warn('Forced build from source')
            node.binary = BINARY_BUILD
            return

        package_folder = self._cache.package(pref,
                                             short_paths=conanfile.short_paths)

        # Check if dirty, to remove it
        local_project = self._workspace[ref] if self._workspace else None
        if local_project:
            node.binary = BINARY_WORKSPACE
            return

        with self._cache.package_lock(pref):
            if is_dirty(package_folder):
                output.warn("Package is corrupted, removing folder: %s" % package_folder)
                assert node.recipe != RECIPE_EDITABLE, "Editable package cannot be dirty"
                rmdir(package_folder)  # Do not remove if it is EDITABLE

        if remote_name:
            remote = self._registry.remotes.get(remote_name)
        else:
            # If the remote_name is not given, follow the binary remote, or
            # the recipe remote
            # If it is defined it won't iterate (might change in conan2.0)
            remote = self._registry.prefs.get(pref) or self._registry.refs.get(ref)
        remotes = self._registry.remotes.list

        if os.path.exists(package_folder):
            if update:
                if remote:
                    if self._check_update(package_folder, pref, remote, output, node):
                        node.binary = BINARY_UPDATE
                        if build_mode.outdated:
                            package_hash = self._get_package_info(pref, remote).recipe_hash
                elif remotes:
                    pass
                else:
                    output.warn("Can't update, no remote defined")
            if not node.binary:
                node.binary = BINARY_CACHE
                package_hash = ConanInfo.load_from_package(package_folder).recipe_hash

        else:  # Binary does NOT exist locally
            if not revisions_enabled and not node.revision_pinned:
                # Do not search for packages for the specific resolved recipe revision but all
                pref = pref.copy_clear_rev()

            remote_info = None
            if remote:
                remote_info = self._get_package_info(pref, remote)

            # If the "remote" came from the registry but the user didn't specified the -r, with
            # revisions iterate all remotes
            if not remote or (not remote_info and revisions_enabled and not remote_name):
                for r in remotes:
                    remote_info = self._get_package_info(pref, r)
                    if remote_info:
                        remote = r
                        break

            if remote_info:
                node.binary = BINARY_DOWNLOAD
                package_hash = remote_info.recipe_hash
            else:
                if build_mode.allowed(conanfile):
                    node.binary = BINARY_BUILD
                else:
                    node.binary = BINARY_MISSING

        if build_mode.outdated:
            if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE):
                local_recipe_hash = self._cache.package_layout(ref).load_manifest().summary_hash
                if local_recipe_hash != package_hash:
                    output.info("Outdated package!")
                    node.binary = BINARY_BUILD
                else:
                    output.info("Package is up to date")

        node.binary_remote = remote

    def evaluate_graph(self, deps_graph, build_mode, update, remote_name):
        evaluated_nodes = {}
        for node in deps_graph.nodes:
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary:
                continue
            private_neighbours = node.private_neighbors()
            if private_neighbours:
                self._evaluate_node(node, build_mode, update, evaluated_nodes, remote_name)
                if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE):
                    for neigh in private_neighbours:
                        neigh.binary = BINARY_SKIP
                        closure = deps_graph.full_closure(neigh, private=True)
                        for n in closure:
                            n.binary = BINARY_SKIP

        for node in deps_graph.nodes:
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary:
                continue
            self._evaluate_node(node, build_mode, update, evaluated_nodes, remote_name)
