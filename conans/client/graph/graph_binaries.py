from conans.client.graph.build_mode import BuildMode
from conans.client.graph.compatibility import BinaryCompatibility
from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_UPDATE, RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, BINARY_UNKNOWN,
                                       BINARY_INVALID)
from conans.errors import NoRemoteAvailable, NotFoundException, conanfile_exception_formatter, \
    ConanException, ConanInvalidConfiguration
from conans.model.info import ConanInfo, PACKAGE_ID_UNKNOWN, PACKAGE_ID_INVALID
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.util.conan_v2_mode import conan_v2_property


class GraphBinariesAnalyzer(object):

    def __init__(self, cache, output, remote_manager):
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager
        # These are the nodes with pref (not including PREV) that have been evaluated
        self._evaluated = {}  # {pref: [nodes]}
        self._fixed_package_id = cache.config.full_transitive_package_id
        self._compatibility = BinaryCompatibility(self._cache)

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
            if node.cant_build:
                node.binary = BINARY_INVALID
            else:
                node.binary = BINARY_BUILD
            node.prev = None
            return True

    def _evaluate_clean_pkg_folder_dirty(self, node, package_layout, pref):
        # Check if dirty, to remove it
        with package_layout.package_lock(pref):
            assert node.recipe != RECIPE_EDITABLE, "Editable package shouldn't reach this code"
            if package_layout.package_is_dirty(pref):
                node.conanfile.output.warn("Package binary is corrupted, removing: %s" % pref.id)
                package_layout.package_remove(pref)
                return

            if self._cache.config.revisions_enabled:
                metadata = package_layout.load_metadata()

                rec_rev = metadata.packages[
                    pref.id].recipe_revision if pref.id in metadata.packages else None

                if rec_rev and rec_rev != node.ref.revision:
                    node.conanfile.output.warn("The package {} doesn't belong to the installed "
                                               "recipe revision, removing folder".format(pref))
                    package_layout.package_remove(pref)
                return metadata

    def _evaluate_cache_pkg(self, node, package_layout, pref, metadata, remote, remotes, update):
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
                    package_folder = package_layout.package(pref)
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

    def _get_package_info(self, node, pref, remote):
        return self._remote_manager.get_package_info(pref, remote, info=node.conanfile.info)

    def _evaluate_remote_pkg(self, node, pref, remote, remotes, remote_selected):
        remote_info = None
        # If the remote is pinned (remote_selected) we won't iterate the remotes.
        # The "remote" can come from -r or from the registry (associated ref)
        if remote_selected or remote:
            try:
                remote_info, pref = self._get_package_info(node, pref, remote)
            except NotFoundException:
                pass
            except Exception:
                node.conanfile.output.error("Error downloading binary package: '{}'".format(pref))
                raise

        # If we didn't pin a remote with -r and:
        #   - The remote is None (not registry entry)
        #        or
        #   - We didn't find a package but having revisions enabled
        # We iterate the other remotes to find a binary
        if not remote_selected and (not remote or
                                    (not remote_info and self._cache.config.revisions_enabled)):
            for r in remotes.values():
                if r == remote:
                    continue
                try:
                    remote_info, pref = self._get_package_info(node, pref, r)
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

            # this line fixed the compatible_packages with private case.
            # https://github.com/conan-io/conan/issues/9880
            node._package_id = previous_node.package_id
            return True
        self._evaluated[pref] = [node]

    def _evaluate_node(self, node, build_mode, update, remotes):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.package_id != PACKAGE_ID_UNKNOWN, "Node.package_id shouldn't be Unknown"
        assert node.prev is None, "Node.prev should be None"

        # If it has lock
        locked = node.graph_lock_node
        if locked and locked.package_id and locked.package_id != PACKAGE_ID_UNKNOWN:
            pref = PackageReference(locked.ref, locked.package_id, locked.prev)  # Keep locked PREV
            self._process_node(node, pref, build_mode, update, remotes)
            if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
                if node.cant_build:
                    node.binary = BINARY_INVALID
                else:
                    node.binary = BINARY_BUILD
            if node.binary == BINARY_BUILD:
                locked.unlock_prev()

            if node.package_id != locked.package_id:  # It was a compatible package
                # https://github.com/conan-io/conan/issues/9002
                # We need to iterate to search the compatible combination
                for compatible_package in node.conanfile.compatible_packages:
                    comp_package_id = compatible_package.package_id()
                    if comp_package_id == locked.package_id:
                        node._package_id = locked.package_id  # FIXME: Ugly definition of private
                        node.conanfile.settings.values = compatible_package.settings
                        node.conanfile.options.values = compatible_package.options
                        break
                else:
                    raise ConanException("'%s' package-id '%s' doesn't match the locked one '%s'"
                                         % (repr(locked.ref), node.package_id, locked.package_id))
        else:
            assert node.prev is None, "Non locked node shouldn't have PREV in evaluate_node"
            assert node.binary is None, "Node.binary should be None if not locked"
            pref = PackageReference(node.ref, node.package_id)
            self._process_node(node, pref, build_mode, update, remotes)
            if node.binary in (BINARY_MISSING, BINARY_INVALID):
                conanfile = node.conanfile
                self._compatibility.compatibles(conanfile)
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
                        if node.binary not in (BINARY_MISSING, ):
                            node.conanfile.output.info("Main binary package '%s' missing. Using "
                                                       "compatible package '%s'"
                                                       % (node.package_id, package_id))

                            # Modifying package id under the hood, FIXME
                            node._package_id = package_id
                            # So they are available in package_info() method
                            node.conanfile.settings.values = compatible_package.settings
                            # TODO: Conan 2.0 clean this ugly
                            node.conanfile.options._package_options.values = compatible_package.options._package_values
                            break
                    if node.binary == BINARY_MISSING and node.package_id == PACKAGE_ID_INVALID:
                        node.binary = BINARY_INVALID
                if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
                    if node.cant_build:
                        node.binary = BINARY_INVALID
                    else:
                        node.binary = BINARY_BUILD

            if locked:
                # package_id was not locked, this means a base lockfile that is being completed
                locked.complete_base_node(node.package_id, node.prev)

    def _process_node(self, node, pref, build_mode, update, remotes):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node, pref):
            return

        conanfile = node.conanfile
        if node.recipe == RECIPE_EDITABLE:
            node.binary = BINARY_EDITABLE  # TODO: PREV?
            return

        if pref.id == PACKAGE_ID_INVALID:
            # annotate pattern, so unused patterns in --build are not displayed as errors
            build_mode.forced(node.conanfile, node.ref)
            node.binary = BINARY_INVALID
            return



        if self._evaluate_build(node, build_mode):
            return

        package_layout = self._cache.package_layout(pref.ref, short_paths=conanfile.short_paths)
        metadata = self._evaluate_clean_pkg_folder_dirty(node, package_layout, pref)

        remote = remotes.selected
        remote_selected = remote is not None

        metadata = metadata or package_layout.load_metadata()
        if not remote:
            # If the remote_name is not given, follow the binary remote, or the recipe remote
            # If it is defined it won't iterate (might change in conan2.0)
            if pref.id in metadata.packages:
                remote_name = metadata.packages[pref.id].remote or metadata.recipe.remote
            else:
                remote_name = metadata.recipe.remote
            remote = remotes.get(remote_name)

        if package_layout.package_id_exists(pref.id) and pref.id in metadata.packages:
            # Binary already in cache, check for updates
            self._evaluate_cache_pkg(node, package_layout, pref, metadata, remote, remotes, update)
            recipe_hash = None
        else:  # Binary does NOT exist locally
            # Returned remote might be different than the passed one if iterating remotes
            recipe_hash, remote = self._evaluate_remote_pkg(node, pref, remote, remotes,
                                                            remote_selected)

        if build_mode.outdated:
            if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE):
                if node.binary == BINARY_UPDATE:
                    info, pref = self._get_package_info(node, pref, remote)
                    recipe_hash = info.recipe_hash
                elif node.binary == BINARY_CACHE:
                    package_folder = package_layout.package(pref)
                    recipe_hash = ConanInfo.load_from_package(package_folder).recipe_hash

                local_recipe_hash = package_layout.recipe_manifest().summary_hash
                if local_recipe_hash != recipe_hash:
                    conanfile.output.info("Outdated package!")
                    if node.cant_build:
                        node.binary = BINARY_INVALID
                    else:
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

        direct_reqs, indirect_reqs = self.package_id_transitive_reqs(node)

        # FIXME: Conan v2.0 This is introducing a bug for backwards compatibility, it will add
        #   only the requirements available in the 'neighbour.info' object, not all the closure
        if not self._fixed_package_id:
            old_indirect = set()
            for neighbor in neighbors:
                old_indirect.update((p.ref, p.id) for p in neighbor.conanfile.info.requires.refs())
            indirect_reqs = set(p for p in indirect_reqs if (p.ref, p.id) in old_indirect)
            indirect_reqs.difference_update(direct_reqs)

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
        conanfile.original_info = conanfile.info.clone()
        if not self._cache.new_config["core.package_id:msvc_visual_incompatible"]:
            msvc_compatible = conanfile.info.msvc_compatible()
            if msvc_compatible:
                conanfile.compatible_packages.append(msvc_compatible)

        apple_clang_compatible = conanfile.info.apple_clang_compatible()
        if apple_clang_compatible:
            conanfile.compatible_packages.append(apple_clang_compatible)

        # Once we are done, call package_id() to narrow and change possible values
        with conanfile_exception_formatter(str(conanfile), "package_id"):
            with conan_v2_property(conanfile, 'cpp_info',
                                   "'self.cpp_info' access in package_id() method is deprecated"):
                conanfile.package_id()

        if hasattr(conanfile, "validate") and callable(conanfile.validate):
            with conanfile_exception_formatter(str(conanfile), "validate"):
                try:
                    conanfile.validate()
                    # FIXME: this shouldn't be necessary in Conan 2.0
                    conanfile._conan_dependencies = None
                except ConanInvalidConfiguration as e:
                    conanfile.info.invalid = str(e)

        if hasattr(conanfile, "validate_build") and callable(conanfile.validate_build):
            with conanfile_exception_formatter(str(conanfile), "validate_build"):
                try:
                    conanfile.validate_build()
                except ConanInvalidConfiguration as e:
                    # This 'cant_build' will be ignored if we don't have to build the node.
                    node.cant_build = str(e)

        info = conanfile.info
        node.package_id = info.package_id()

    def evaluate_graph(self, deps_graph, build_mode, update, remotes, nodes_subset=None, root=None):
        default_package_id_mode = self._cache.config.default_package_id_mode
        default_python_requires_id_mode = self._cache.config.default_python_requires_id_mode
        for node in deps_graph.ordered_iterate(nodes_subset=nodes_subset):
            self._propagate_options(node)

            # Make sure that locked options match
            if (node.graph_lock_node is not None and
                    node.graph_lock_node.options is not None and
                    node.conanfile.options.values != node.graph_lock_node.options):
                raise ConanException("{}: Locked options do not match computed options\n"
                                     "Locked options:\n{}\n"
                                     "Computed options:\n{}".format(node.ref,
                                                                    node.graph_lock_node.options,
                                                                    node.conanfile.options.values))

            self._compute_package_id(node, default_package_id_mode, default_python_requires_id_mode)
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            if node.package_id == PACKAGE_ID_UNKNOWN:
                assert node.binary is None, "Node.binary should be None"
                node.binary = BINARY_UNKNOWN
                # annotate pattern, so unused patterns in --build are not displayed as errors
                build_mode.forced(node.conanfile, node.ref)
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
