from conans.client.graph.build_mode import BuildMode
from conans.client.graph.compatibility import BinaryCompatibility
from conans.client.graph.compute_pid import compute_package_id
from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_UPDATE, RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP,
                                       BINARY_INVALID, BINARY_EDITABLE_BUILD)
from conans.errors import NoRemoteAvailable, NotFoundException, \
    PackageNotFoundException, conanfile_exception_formatter


class GraphBinariesAnalyzer(object):

    def __init__(self, conan_app):
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        # These are the nodes with pref (not including PREV) that have been evaluated
        self._evaluated = {}  # {pref: [nodes]}
        self._compatibility = BinaryCompatibility(self._cache)

    @staticmethod
    def _evaluate_build(node, build_mode):
        ref, conanfile = node.ref, node.conanfile
        with_deps_to_build = False
        # For cascade mode, we need to check also the "modified" status of the lockfile if exists
        # modified nodes have already been built, so they shouldn't be built again
        if build_mode.cascade:
            for dep in node.dependencies:
                dep_node = dep.dst
                if dep_node.binary == BINARY_BUILD:
                    with_deps_to_build = True
                    break
        if build_mode.forced(conanfile, ref, with_deps_to_build):
            node.should_build = True
            conanfile.output.info('Forced build from source')
            node.binary = BINARY_BUILD if not node.cant_build else BINARY_INVALID
            node.prev = None
            return True

    @staticmethod
    def _evaluate_clean_pkg_folder_dirty(node, package_layout):
        # Check if dirty, to remove it
        with package_layout.package_lock():
            assert node.recipe != RECIPE_EDITABLE, "Editable package shouldn't reach this code"
            if package_layout.package_is_dirty():
                node.conanfile.output.warning("Package binary is corrupted, "
                                              "removing: %s" % node.package_id)
                package_layout.package_remove()
                return True

    # check through all the selected remotes:
    # - if not --update: get the first package found
    # - if --update: get the latest remote searching in all of them
    def _get_package_from_remotes(self, node):
        results = []
        pref = node.pref
        for r in self._selected_remotes:
            try:
                latest_pref = self._remote_manager.get_latest_package_reference(pref, r)
                results.append({'pref': latest_pref, 'remote': r})
                if len(results) > 0 and not self._update:
                    break
            except NotFoundException:
                pass

        if not self._selected_remotes and self._update:
            node.conanfile.output.warning("Can't update, there are no remotes defined")

        if len(results) > 0:
            remotes_results = sorted(results, key=lambda k: k['pref'].timestamp, reverse=True)
            result = remotes_results[0]
            node.prev = result.get("pref").revision
            node.pref_timestamp = result.get("pref").timestamp
            node.binary_remote = result.get('remote')
        else:
            node.binary_remote = None
            node.prev = None
            raise PackageNotFoundException(pref)

    def _evaluate_is_cached(self, node):
        """ Each pref has to be evaluated just once, and the action for all of them should be
        exactly the same
        """
        pref = node.pref
        previous_nodes = self._evaluated.get(pref)
        if previous_nodes:
            previous_nodes.append(node)
            previous_node = previous_nodes[0]
            node.binary = previous_node.binary
            node.binary_remote = previous_node.binary_remote
            node.prev = previous_node.prev
            node.pref_timestamp = previous_node.pref_timestamp

            # this line fixed the compatible_packages with private case.
            # https://github.com/conan-io/conan/issues/9880
            node._package_id = previous_node.package_id
            return True
        self._evaluated[pref] = [node]

    def _process_compatible_packages(self, node):
        conanfile = node.conanfile
        original_binary = node.binary
        original_package_id = node.package_id

        compatibles = self._compatibility.compatibles(conanfile)
        existing = compatibles.pop(original_package_id, None)   # Skip main package_id
        if existing:  # Skip the check if same packge_id
            conanfile.output.info(f"Compatible package ID {original_package_id} equal to "
                                  "the default package ID")

        if compatibles:
            conanfile.output.info(f"Checking {len(compatibles)} compatible configurations:")
        for package_id, compatible_package in compatibles.items():
            conanfile.output.info(f"'{package_id}': "
                                  f"{conanfile.info.dump_diff(compatible_package)}")
            node._package_id = package_id  # Modifying package id under the hood, FIXME
            node.binary = None  # Invalidate it
            self._process_compatible_node(node)
            if node.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE):
                conanfile.output.info("Main binary package '%s' missing. Using "
                                      "compatible package '%s'" % (original_package_id, package_id))
                # So they are available in package_info() method
                conanfile.info = compatible_package  # Redefine current
                conanfile.settings.update_values(compatible_package.settings.values_list)
                # Trick to allow mutating the options (they were freeze=True)
                # TODO: Improve this interface
                conanfile.options = conanfile.options.copy_conaninfo_options()
                conanfile.options.update_options(compatible_package.options)
                break
        else:  # If no compatible is found, restore original state
            node.binary = original_binary
            node._package_id = original_package_id

    def _evaluate_node(self, node, build_mode):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.prev is None, "Node.prev should be None"

        self._process_node(node, build_mode)
        if node.binary in (BINARY_MISSING,) \
                and not build_mode.should_build_missing(node.conanfile) and not node.should_build:
            self._process_compatible_packages(node)

        if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
            node.should_build = True
            node.binary = BINARY_BUILD if not node.cant_build else BINARY_INVALID

        if (node.binary in (BINARY_BUILD, BINARY_MISSING) and node.conanfile.info.invalid and
                node.conanfile.info.invalid[0] == BINARY_INVALID):
            # BINARY_BUILD IS NOT A VIABLE fallback for invalid
            node.binary = BINARY_INVALID

    def _process_node(self, node, build_mode):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node):
            return

        if node.conanfile.info.invalid:
            node.binary = BINARY_INVALID
            return

        if node.recipe == RECIPE_EDITABLE:
            # TODO: Check what happens when editable is passed an Invalid configuration
            if build_mode.editable or self._evaluate_build(node, build_mode) or \
                    build_mode.should_build_missing(node.conanfile):
                node.binary = BINARY_EDITABLE_BUILD
            else:
                node.binary = BINARY_EDITABLE  # TODO: PREV?
            return

        # If the CLI says this package needs to be built, it doesn't make sense to mark
        # it as invalid
        if self._evaluate_build(node, build_mode):
            return

        # Obtain the cache_latest valid one, cleaning things if dirty
        while True:
            cache_latest_prev = self._cache.get_latest_package_reference(node.pref)
            if cache_latest_prev is None:
                break
            package_layout = self._cache.pkg_layout(cache_latest_prev)
            if not self._evaluate_clean_pkg_folder_dirty(node, package_layout):
                break

        if cache_latest_prev is None:  # This binary does NOT exist in the cache
            self._evaluate_download(node)
        else:  # This binary already exists in the cache, maybe can be updated
            self._evaluate_in_cache(cache_latest_prev, node)

        # The INVALID should only prevail if a compatible package, due to removal of
        # settings in package_id() was not found
        if node.binary in (BINARY_MISSING, BINARY_BUILD):
            if node.conanfile.info.invalid and node.conanfile.info.invalid[0] == BINARY_INVALID:
                node.binary = BINARY_INVALID

    def _process_compatible_node(self, node):
        """ simplified checking of compatible_packages, that should be found existing, but
        will never be built, for example. They cannot be editable either at this point.
        """
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node):
            return

        # TODO: Test that this works
        if node.conanfile.info.invalid:
            node.binary = BINARY_INVALID
            return

        # Obtain the cache_latest valid one, cleaning things if dirty
        while True:
            cache_latest_prev = self._cache.get_latest_package_reference(node.pref)
            if cache_latest_prev is None:
                break
            package_layout = self._cache.pkg_layout(cache_latest_prev)
            if not self._evaluate_clean_pkg_folder_dirty(node, package_layout):
                break

        if cache_latest_prev is None:  # This binary does NOT exist in the cache
            self._evaluate_download(node)
        else:  # This binary already exists in the cache, maybe can be updated
            self._evaluate_in_cache(cache_latest_prev, node)

    def _process_locked_node(self, node, build_mode, locked_prev):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node):
            return

        # If the CLI says this package needs to be built, it doesn't make sense to mark
        # it as invalid
        if self._evaluate_build(node, build_mode):
            # TODO: We migth want to rais if strict
            return

        if node.recipe == RECIPE_EDITABLE:
            # TODO: Raise if strict
            node.binary = BINARY_EDITABLE  # TODO: PREV?
            return

        # in cache:
        node.prev = locked_prev
        if self._cache.exists_prev(node.pref):
            node.binary = BINARY_CACHE
            node.binary_remote = None
            # TODO: Dirty
            return

        # TODO: Check in remotes for download

    def _evaluate_download(self, node):
        try:
            self._get_package_from_remotes(node)
        except NotFoundException:
            node.binary = BINARY_MISSING
        else:
            node.binary = BINARY_DOWNLOAD

    def _evaluate_in_cache(self, cache_latest_prev, node):
        assert cache_latest_prev.revision
        if self._update:
            output = node.conanfile.output
            try:
                self._get_package_from_remotes(node)
            except NotFoundException:
                output.warning("Can't update, no package in remote")
            except NoRemoteAvailable:
                output.warning("Can't update, there are no remotes configured or enabled")
            else:
                cache_time = cache_latest_prev.timestamp
                # TODO: cache 2.0 should we update the date if the prev is the same?
                if cache_time < node.pref_timestamp and cache_latest_prev != node.pref:
                    node.binary = BINARY_UPDATE
                    output.info("Current package revision is older than the remote one")
                else:
                    node.binary = BINARY_CACHE
                    # The final data is the cache one, not the server one
                    node.binary_remote = None
                    node.prev = cache_latest_prev.revision
                    node.pref_timestamp = cache_time
                    output.info("Current package revision is newer than the remote one")
        if not node.binary:
            node.binary = BINARY_CACHE
            node.binary_remote = None
            node.prev = cache_latest_prev.revision
            assert node.prev, "PREV for %s is None" % str(node.pref)

    def _evaluate_package_id(self, node):
        compute_package_id(node, self._cache.new_config)  # TODO: revise compute_package_id()

        # TODO: layout() execution don't need to be evaluated at GraphBuilder time.
        # it could even be delayed until installation time, but if we got enough info here for
        # package_id, we can run it
        conanfile = node.conanfile
        if hasattr(conanfile, "layout"):
            with conanfile_exception_formatter(conanfile, "layout"):
                conanfile.layout()

    def evaluate_graph(self, deps_graph, build_mode, lockfile, remotes, update):
        self._selected_remotes = remotes or []# TODO: A bit dirty interfaz, pass as arg instead
        self._update = update  # TODO: Dirty, fix it
        build_mode = BuildMode(build_mode)
        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                if node.path is not None and node.path.endswith(".py"):
                    # For .py we keep evaluating the package_id, validate(), etc
                    self._evaluate_package_id(node)
                elif node.path is not None and node.path.endswith(".txt"):
                    # To support the ``[layout]`` in conanfile.txt
                    # TODO: Refactorize this a bit, the call to ``layout()``
                    if hasattr(node.conanfile, "layout"):
                        with conanfile_exception_formatter(node.conanfile, "layout"):
                            node.conanfile.layout()
            else:
                self._evaluate_package_id(node)
                if lockfile:
                    locked_prev = lockfile.resolve_prev(node)
                    if locked_prev:
                        self._process_locked_node(node, build_mode, locked_prev)
                        continue
                self._evaluate_node(node, build_mode)

        self._skip_binaries(deps_graph)

    @staticmethod
    def _skip_binaries(graph):
        required_nodes = set()
        required_nodes.add(graph.root)
        for node in graph.nodes:
            if node.binary != BINARY_BUILD and node is not graph.root:
                continue
            for req, dep in node.transitive_deps.items():
                dep_node = dep.node
                require = dep.require
                if not require.skip:
                    required_nodes.add(dep_node)

        for node in graph.nodes:
            if node not in required_nodes:
                node.binary = BINARY_SKIP
