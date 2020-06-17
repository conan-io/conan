import os

from conans import DEFAULT_REVISION_V1
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_UPDATE, RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, BINARY_UNKNOWN)
from conans.errors import NoRemoteAvailable, NotFoundException, conanfile_exception_formatter, \
    ConanException
from conans.model.info import ConanInfo, PACKAGE_ID_UNKNOWN
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.util.conan_v2_mode import conan_v2_property
from conans.util.files import is_dirty, rmdir


class GraphBinariesAnalyzer(object):

    def __init__(self, cache, output, remote_manager):
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager
        # These are the nodes with pref (not including PREV) that have been evaluated
        self._evaluated = {}  # {pref: [nodes]}
        self._fixed_package_id = cache.config.full_transitive_package_id

    @staticmethod
    def _check_update(upstream_manifest, package_folder, output):
        read_manifest = FileTreeManifest.load(package_folder)
        if upstream_manifest != read_manifest:
            if upstream_manifest.time > read_manifest.time:
                output.warn("Current package is older than remote upstream one")
                return True
            else:
                output.warn("Current package is newer than remote upstream one")

    @staticmethod
    def _evaluate_build(node, build_mode):
        ref, conanfile = node.ref, node.conanfile
        with_deps_to_build = False
        # For cascade mode, we need to check also the "modified" status of the lockfile if exists
        # modified nodes have already been built, so they shouldn't be built again
        if build_mode.cascade and not (node.graph_lock_node and node.graph_lock_node.modified):
            for dep in node.dependencies:
                dep_node = dep.dst
                if (dep_node.binary == BINARY_BUILD or
                        (dep_node.graph_lock_node and dep_node.graph_lock_node.modified)):
                    with_deps_to_build = True
                    break
        if build_mode.forced(conanfile, ref, with_deps_to_build):
            conanfile.output.info('Forced build from source')
            node.binary = BINARY_BUILD
            node.prev = None
            return True

    def _evaluate_clean_pkg_folder_dirty(self, node, package_layout, package_folder, pref):
        # Check if dirty, to remove it
        with package_layout.package_lock(pref):
            assert node.recipe != RECIPE_EDITABLE, "Editable package shouldn't reach this code"
            if is_dirty(package_folder):
                node.conanfile.output.warn("Package is corrupted, removing folder: %s"
                                           % package_folder)
                rmdir(package_folder)  # Do not remove if it is EDITABLE
                return

            if self._cache.config.revisions_enabled:
                metadata = package_layout.load_metadata()
                rec_rev = metadata.packages[pref.id].recipe_revision
                if rec_rev and rec_rev != node.ref.revision:
                    node.conanfile.output.warn("The package {} doesn't belong to the installed "
                                               "recipe revision, removing folder".format(pref))
                    rmdir(package_folder)
                return metadata

    def _evaluate_cache_pkg(self, node, package_layout, pref, metadata, remote, remotes, update,
                            package_folder):
        if update:
            output = node.conanfile.output
            if remote:
                try:
                    tmp = self._remote_manager.get_package_manifest(pref, remote)
                    upstream_manifest, pref = tmp
                except NotFoundException:
                    output.warn("Can't update, no package in remote")
                except NoRemoteAvailable:
                    output.warn("Can't update, no remote defined")
                else:
                    if self._check_update(upstream_manifest, package_folder, output):
                        node.binary = BINARY_UPDATE
                        node.prev = pref.revision  # With revision
            elif remotes:
                pass  # Current behavior: no remote explicit or in metadata, do not update
            else:
                output.warn("Can't update, no remote defined")
        if not node.binary:
            node.binary = BINARY_CACHE
            metadata = metadata or package_layout.load_metadata()
            node.prev = metadata.packages[pref.id].revision
            assert node.prev, "PREV for %s is None: %s" % (str(pref), metadata.dumps())

    def _evaluate_remote_pkg(self, node, pref, remote, remotes):
        remote_info = None
        if remote:
            try:
                remote_info, pref = self._remote_manager.get_package_info(pref, remote)
            except NotFoundException:
                pass
            except Exception:
                node.conanfile.output.error("Error downloading binary package: '{}'".format(pref))
                raise

        # If the "remote" came from the registry but the user didn't specified the -r, with
        # revisions iterate all remotes
        if not remote or (not remote_info and self._cache.config.revisions_enabled):
            for r in remotes.values():
                try:
                    remote_info, pref = self._remote_manager.get_package_info(pref, r)
                except NotFoundException:
                    pass
                else:
                    if remote_info:
                        remote = r
                        break

        if remote_info:
            node.binary = BINARY_DOWNLOAD
            node.prev = pref.revision
            recipe_hash = remote_info.recipe_hash
        else:
            recipe_hash = None
            node.prev = None
            node.binary = BINARY_MISSING

        return recipe_hash, remote

    def _evaluate_is_cached(self, node, pref):
        previous_nodes = self._evaluated.get(pref)
        if previous_nodes:
            previous_nodes.append(node)
            previous_node = previous_nodes[0]
            # The previous node might have been skipped, but current one not necessarily
            # keep the original node.binary value (before being skipped), and if it will be
            # defined as SKIP again by self._handle_private(node) if it is really private
            if previous_node.binary == BINARY_SKIP:
                node.binary = previous_node.binary_non_skip
            else:
                node.binary = previous_node.binary
            node.binary_remote = previous_node.binary_remote
            node.prev = previous_node.prev
            return True
        self._evaluated[pref] = [node]

    def _evaluate_node(self, node, build_mode, update, remotes):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.package_id != PACKAGE_ID_UNKNOWN, "Node.package_id shouldn't be Unknown"
        assert node.prev is None, "Node.prev should be None"

        # If it has lock
        locked = node.graph_lock_node
        if locked:
            assert locked.ref.copy_clear_rev() == node.ref.copy_clear_rev(), "%s != %s" % (repr(locked.ref), repr(node.ref))

            if locked.package_id:
                if locked.package_id != node.package_id:
                    raise ConanException("Lockfile error in '%s'. The locked package_id '%s' "
                                         "does not match the graph '%s'"
                                         % (node.ref, locked.package_id, node.package_id))

                need_build = self._evaluate_build(node, build_mode)
                if locked.prev is not None:  # The actual package PREV is fully locked, find it
                    if need_build:
                        raise ConanException("Trying to build '%s', but it is locked"
                                             % repr(node.ref))
                    #prev = None if locked.prev == DEFAULT_REVISION_V1 else locked.prev
                    #ref = locked.ref.copy_clear_rev() if locked.ref.revision == DEFAULT_REVISION_V1 else locked.ref
                    pref = PackageReference(locked.ref, locked.package_id, locked.prev)
                    print("FINDING LOCKED NODE ", repr(pref), remotes)
                    self._find_locked_node(node, pref, remotes)
                else:  # prev = None could be not locked or locked but not using revisions
                    if not need_build:
                        node.binary = BINARY_MISSING
                return

        assert node.prev is None, "Non locked node shouldn't have PREV in evaluate_node"
        assert node.binary is None, "Node.binary should be None if not locked"
        pref = PackageReference(node.ref, node.package_id)
        self._process_node(node, pref, build_mode, update, remotes)
        if node.binary == BINARY_MISSING:
            if node.conanfile.compatible_packages:
                compatible_build_mode = BuildMode(None, self._out)
                for compatible_package in node.conanfile.compatible_packages:
                    package_id = compatible_package.package_id()
                    if package_id == node.package_id:
                        node.conanfile.output.info("Compatible package ID %s equal to the "
                                                   "default package ID" % package_id)
                        continue
                    pref = PackageReference(node.ref, package_id)
                    node.binary = None  # Invalidate it
                    # NO Build mode
                    self._process_node(node, pref, compatible_build_mode, update, remotes)
                    assert node.binary is not None
                    if node.binary != BINARY_MISSING:
                        node.conanfile.output.info("Main binary package '%s' missing. Using "
                                                   "compatible package '%s'"
                                                   % (node.package_id, package_id))
                        # Modifying package id under the hood, FIXME
                        node._package_id = package_id
                        # So they are available in package_info() method
                        node.conanfile.settings.values = compatible_package.settings
                        node.conanfile.options.values = compatible_package.options
                        break
            if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
                node.binary = BINARY_BUILD

        if locked:
            locked.package_id = node.package_id
            locked.prev = node.prev

    def _find_locked_node(self, node, pref, remotes):
        # When the lock contains a PREV, it means it cannot be built
        if self._evaluate_is_cached(node, pref):
            return

        conanfile = node.conanfile

        package_layout = self._cache.package_layout(pref.ref, short_paths=conanfile.short_paths)
        metadata = package_layout.load_metadata()
        if self._cache.config.revisions_enabled:
            assert metadata.recipe.revision == node.ref.revision
            if metadata.packages[pref.id].revision == pref.revision:
                node.binary = BINARY_CACHE
                node.prev = pref.revision
                return
        else:
            package_folder = package_layout.package(pref)
            if os.path.exists(package_folder):
                node.binary = BINARY_CACHE
                node.prev = pref.revision
                return

        def _search_in_remote(r):
            print("SEARCHING IN REMOTE ", r.name)
            try:
                remote_info, _pref_result = self._remote_manager.get_package_info(pref, r)
                assert _pref_result == pref
                node.binary = BINARY_DOWNLOAD
                node.binary_remote = r
                node.prev = pref.revision
            except NotFoundException:
                print("NOT FOUND IN REMOTE")
                return None

        selected = remotes.selected
        if selected:
            _search_in_remote(selected)

        for remote in remotes.values():
            if node.binary_remote is None and remote != selected:
                _search_in_remote(remote)

        if node.binary is None:
            raise ConanException("Locked package revision not found %s" % repr(pref))

    def _process_node(self, node, pref, build_mode, update, remotes):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node, pref):
            return

        conanfile = node.conanfile
        if node.recipe == RECIPE_EDITABLE:
            node.binary = BINARY_EDITABLE  # TODO: PREV?
            return

        if self._evaluate_build(node, build_mode):
            return

        package_layout = self._cache.package_layout(pref.ref, short_paths=conanfile.short_paths)
        package_folder = package_layout.package(pref)
        metadata = self._evaluate_clean_pkg_folder_dirty(node, package_layout, package_folder, pref)

        remote = remotes.selected
        if not remote:
            # If the remote_name is not given, follow the binary remote, or the recipe remote
            # If it is defined it won't iterate (might change in conan2.0)
            metadata = metadata or package_layout.load_metadata()
            remote_name = metadata.packages[pref.id].remote or metadata.recipe.remote
            remote = remotes.get(remote_name)

        if os.path.exists(package_folder):  # Binary already in cache, check for updates
            self._evaluate_cache_pkg(node, package_layout, pref, metadata,  remote, remotes, update,
                                     package_folder)
            recipe_hash = None
        else:  # Binary does NOT exist locally
            # Returned remote might be different than the passed one if iterating remotes
            recipe_hash, remote = self._evaluate_remote_pkg(node, pref, remote, remotes)

        if build_mode.outdated:
            if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE):
                if node.binary == BINARY_UPDATE:
                    info, pref = self._remote_manager.get_package_info(pref, remote)
                    recipe_hash = info.recipe_hash
                elif node.binary == BINARY_CACHE:
                    recipe_hash = ConanInfo.load_from_package(package_folder).recipe_hash

                local_recipe_hash = package_layout.recipe_manifest().summary_hash
                if local_recipe_hash != recipe_hash:
                    conanfile.output.info("Outdated package!")
                    node.binary = BINARY_BUILD
                    node.prev = None
                else:
                    conanfile.output.info("Package is up to date")

        node.binary_remote = remote

    @staticmethod
    def _propagate_options(node):
        # TODO: This has to be moved to the graph computation, not here in the BinaryAnalyzer
        # as this is the graph model
        conanfile = node.conanfile
        neighbors = node.neighbors()
        transitive_reqs = set()  # of PackageReference, avoid duplicates
        for neighbor in neighbors:
            ref, nconan = neighbor.ref, neighbor.conanfile
            transitive_reqs.add(neighbor.pref)
            transitive_reqs.update(nconan.info.requires.refs())

            conanfile.options.propagate_downstream(ref, nconan.info.full_options)
            # Update the requirements to contain the full revision. Later in lockfiles
            conanfile.requires[ref.name].ref = ref

        # There might be options that are not upstream, backup them, might be for build-requires
        conanfile.build_requires_options = conanfile.options.values
        conanfile.options.clear_unused(transitive_reqs)
        conanfile.options.freeze()

    @staticmethod
    def package_id_transitive_reqs(node):
        """
        accumulate the direct and transitive requirements prefs necessary to compute the
        package_id
        :return: set(prefs) of direct deps, set(prefs) of transitive deps
        """
        node.id_direct_prefs = set()  # of PackageReference
        node.id_indirect_prefs = set()  # of PackageReference, avoid duplicates
        neighbors = [d.dst for d in node.dependencies if not d.build_require]
        for neighbor in neighbors:
            node.id_direct_prefs.add(neighbor.pref)
            node.id_indirect_prefs.update(neighbor.id_direct_prefs)
            node.id_indirect_prefs.update(neighbor.id_indirect_prefs)
        # Make sure not duplicated, totally necessary
        node.id_indirect_prefs.difference_update(node.id_direct_prefs)
        return node.id_direct_prefs, node.id_indirect_prefs

    def _compute_package_id(self, node, default_package_id_mode, default_python_requires_id_mode):
        """
        Compute the binary package ID of this node
        :param node: the node to compute the package-ID
        :param default_package_id_mode: configuration of the package-ID mode
        """
        # TODO Conan 2.0. To separate the propagation of the graph (options) of the package-ID
        # A bit risky to be done now
        conanfile = node.conanfile
        neighbors = node.neighbors()
        if not self._fixed_package_id:
            direct_reqs = []  # of PackageReference
            indirect_reqs = set()  # of PackageReference, avoid duplicates
            for neighbor in neighbors:
                ref, nconan = neighbor.ref, neighbor.conanfile
                direct_reqs.append(neighbor.pref)
                indirect_reqs.update(nconan.info.requires.refs())
            # Make sure not duplicated
            indirect_reqs.difference_update(direct_reqs)
        else:
            direct_reqs, indirect_reqs = self.package_id_transitive_reqs(node)

        python_requires = getattr(conanfile, "python_requires", None)
        if python_requires:
            if isinstance(python_requires, dict):
                python_requires = None  # Legacy python-requires do not change package-ID
            else:
                python_requires = python_requires.all_refs()
        conanfile.info = ConanInfo.create(conanfile.settings.values,
                                          conanfile.options.values,
                                          direct_reqs,
                                          indirect_reqs,
                                          default_package_id_mode=default_package_id_mode,
                                          python_requires=python_requires,
                                          default_python_requires_id_mode=
                                          default_python_requires_id_mode)

        # Once we are done, call package_id() to narrow and change possible values
        with conanfile_exception_formatter(str(conanfile), "package_id"):
            with conan_v2_property(conanfile, 'cpp_info',
                                   "'self.cpp_info' access in package_id() method is deprecated"):
                conanfile.package_id()

        info = conanfile.info
        node.package_id = info.package_id()

    def evaluate_graph(self, deps_graph, build_mode, update, remotes, nodes_subset=None, root=None):
        default_package_id_mode = self._cache.config.default_package_id_mode
        default_python_requires_id_mode = self._cache.config.default_python_requires_id_mode
        for node in deps_graph.ordered_iterate(nodes_subset=nodes_subset):
            self._propagate_options(node)

            self._compute_package_id(node, default_package_id_mode, default_python_requires_id_mode)
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            if node.package_id == PACKAGE_ID_UNKNOWN:
                assert node.binary is None, "Node.binary should be None"
                node.binary = BINARY_UNKNOWN
                continue
            self._evaluate_node(node, build_mode, update, remotes)
        deps_graph.mark_private_skippable(nodes_subset=nodes_subset, root=root)

    def reevaluate_node(self, node, remotes, build_mode, update):
        """ reevaluate the node is necessary when there is some PACKAGE_ID_UNKNOWN due to
        package_revision_mode
        """
        assert node.binary == BINARY_UNKNOWN
        output = node.conanfile.output
        node._package_id = None  # Invalidate it, so it can be re-computed
        default_package_id_mode = self._cache.config.default_package_id_mode
        default_python_requires_id_mode = self._cache.config.default_python_requires_id_mode
        output.info("Unknown binary for %s, computing updated ID" % str(node.ref))
        self._compute_package_id(node, default_package_id_mode, default_python_requires_id_mode)
        output.info("Updated ID: %s" % node.package_id)
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            return
        assert node.package_id != PACKAGE_ID_UNKNOWN
        node.binary = None  # Necessary to invalidate so it is properly evaluated
        self._evaluate_node(node, build_mode, update, remotes)
        output.info("Binary for updated ID from: %s" % node.binary)
        if node.binary == BINARY_BUILD:
            output.info("Binary for the updated ID has to be built")
        else:
            output.info("Binary for the updated ID from: %s" % node.binary)
