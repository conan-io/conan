from conans.client.graph.build_mode import BuildMode
from conans.client.graph.compute_pid import compute_package_id
from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_UPDATE, RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, BINARY_UNKNOWN,
                                       BINARY_INVALID, BINARY_ERROR)
from conans.errors import NoRemoteAvailable, NotFoundException, \
    PackageNotFoundException, conanfile_exception_formatter
from conans.model.info import PACKAGE_ID_UNKNOWN, PACKAGE_ID_INVALID
from conans.model.package_ref import PkgReference


class GraphBinariesAnalyzer(object):

    def __init__(self, conan_app):
        self._app = conan_app
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        # These are the nodes with pref (not including PREV) that have been evaluated
        self._evaluated = {}  # {pref: [nodes]}

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
            conanfile.output.info('Forced build from source')
            node.binary = BINARY_BUILD
            node.prev = None
            return True

    def _evaluate_clean_pkg_folder_dirty(self, node, package_layout, pref):
        # Check if dirty, to remove it
        with package_layout.package_lock():
            assert node.recipe != RECIPE_EDITABLE, "Editable package shouldn't reach this code"
            if package_layout.package_is_dirty():
                node.conanfile.output.warning("Package binary is corrupted, "
                                              "removing: %s" % pref.package_id)
                package_layout.package_remove()
                return

    # if we have a remote.selected then do not search in other remotes
    # and error if it's not in the selected
    # otherwise if we did not pin a remote:
    # - if not --update: get the first package found
    # - if --update: get the latest remote searching in all of them
    def _get_package_from_remotes(self, node, pref):
        remote = self._app.selected_remote
        if remote:
            try:
                info = node.conanfile.info
                pref_rev = self._remote_manager.get_latest_package_revision_with_time(pref, remote,
                                                                                      info=info)
                pref.revision = pref_rev.revision
                pref.timestamp = pref_rev.timestamp
                return remote
            except Exception:
                node.conanfile.output.error("Error downloading binary package: '{}'".format(pref))
                raise

        results = []
        for r in self._app.enabled_remotes:
            try:
                latest_pref, latest_time = self._remote_manager.get_latest_package_revision(pref, r)
                results.append({'pref': latest_pref, 'time': latest_time, 'remote': r})
                if len(results) > 0 and not self._app.update:
                    break
            except NotFoundException:
                pass

        if not self._app.enabled_remotes and self._app.update:
            node.conanfile.output.warning("Can't update, there are no remotes configured or enabled")

        if len(results) > 0:
            remotes_results = sorted(results, key=lambda k: k['time'], reverse=True)
            result = remotes_results[0]
            pref.revision = result.get("pref").revision
            pref.timestamp = result.get("time")
            return result.get('remote')
        else:
            raise PackageNotFoundException(pref)

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

    def _evaluate_node(self, node, build_mode):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.package_id != PACKAGE_ID_UNKNOWN, "Node.package_id shouldn't be Unknown"
        assert node.prev is None, "Node.prev should be None"

        if True:  # legacy removal, to avoid huge diff
            assert node.prev is None, "Non locked node shouldn't have PREV in evaluate_node"
            assert node.binary is None, "Node.binary should be None if not locked"
            pref = PkgReference(node.ref, node.package_id)
            self._process_node(node, pref, build_mode)
            if node.binary in (BINARY_MISSING, BINARY_INVALID):
                if node.conanfile.compatible_packages:
                    compatible_build_mode = BuildMode(None)
                    for compatible_package in node.conanfile.compatible_packages:
                        package_id = compatible_package.package_id()
                        if package_id == node.package_id:
                            node.conanfile.output.info("Compatible package ID %s equal to the "
                                                       "default package ID" % package_id)
                            continue
                        pref = PkgReference(node.ref, package_id)
                        node.binary = None  # Invalidate it
                        # NO Build mode
                        self._process_node(node, pref, compatible_build_mode)
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
                            node.conanfile.options._package_options = compatible_package.options._package_options
                            break
                    if node.binary == BINARY_MISSING and node.package_id == PACKAGE_ID_INVALID:
                        node.binary = BINARY_INVALID
                if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
                    node.binary = BINARY_BUILD

        if (node.binary in (BINARY_BUILD, BINARY_MISSING) and node.conanfile.info.invalid and
                node.conanfile.info.invalid[0] == BINARY_INVALID):
            node._package_id = PACKAGE_ID_INVALID  # Fixme: Hack
            node.binary = BINARY_INVALID

    def _process_node(self, node, pref, build_mode):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node, pref):
            return

        if node.conanfile.info.invalid and node.conanfile.info.invalid[0] == BINARY_ERROR:
            node.binary = BINARY_ERROR
            return

        if node.recipe == RECIPE_EDITABLE:
            node.binary = BINARY_EDITABLE  # TODO: PREV?
            return

        if pref.package_id == PACKAGE_ID_INVALID:
            # annotate pattern, so unused patterns in --build are not displayed as errors
            build_mode.forced(node.conanfile, node.ref)
            node.binary = BINARY_INVALID
            return

        if self._evaluate_build(node, build_mode):
            return

        cache_latest_prev = self._cache.get_latest_prev(pref)
        output = node.conanfile.output

        if not cache_latest_prev:
            try:
                remote = self._get_package_from_remotes(node, pref)
            except NotFoundException:
                node.binary = BINARY_MISSING
                node.prev = None
                node.binary_remote = None
            else:
                node.binary = BINARY_DOWNLOAD
                node.prev = pref.revision
                node.binary_remote = remote
        else:
            package_layout = self._cache.pkg_layout(cache_latest_prev)
            self._evaluate_clean_pkg_folder_dirty(node, package_layout, pref)
            if self._app.update:
                try:
                    remote = self._get_package_from_remotes(node, pref)
                except NotFoundException:
                    output.warning("Can't update, no package in remote")
                except NoRemoteAvailable:
                    output.warning("Can't update, there are no remotes configured or enabled")
                else:
                    cache_time = self._cache.get_package_timestamp(cache_latest_prev)
                    # TODO: cache 2.0 should we update the date if the prev is the same?
                    if cache_time < pref.timestamp and cache_latest_prev != pref:
                        node.binary = BINARY_UPDATE
                        node.prev = pref.revision
                        node.binary_remote = remote
                        output.info("Current package revision is older than the remote one")
                    else:
                        node.binary = BINARY_CACHE
                        node.binary_remote = None
                        node.prev = cache_latest_prev.revision
                        output.info("Current package revision is newer than the remote one")

            if not node.binary:
                node.binary = BINARY_CACHE
                node.binary_remote = None
                node.prev = cache_latest_prev.revision
                assert node.prev, "PREV for %s is None" % str(pref)

    def _evaluate_package_id(self, node):
        compute_package_id(node, self._cache.new_config)  # TODO: revise compute_package_id()

        # TODO: layout() execution don't need to be evaluated at GraphBuilder time.
        # it could even be delayed until installation time, but if we got enough info here for
        # package_id, we can run it
        conanfile = node.conanfile
        if hasattr(conanfile, "layout"):
            with conanfile_exception_formatter(str(conanfile), "layout"):
                conanfile.layout()

    def evaluate_graph(self, deps_graph, build_mode):

        build_mode = BuildMode(build_mode)
        assert isinstance(build_mode, BuildMode)

        for node in deps_graph.ordered_iterate():
            self._evaluate_package_id(node)
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            if node.package_id == PACKAGE_ID_UNKNOWN:
                assert node.binary is None, "Node.binary should be None"
                node.binary = BINARY_UNKNOWN
                # annotate pattern, so unused patterns in --build are not displayed as errors
                build_mode.forced(node.conanfile, node.ref)
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
                if require.headers or require.libs or require.run or require.build:
                    required_nodes.add(dep_node)

        for node in graph.nodes:
            if node not in required_nodes:
                node.binary = BINARY_SKIP

    def reevaluate_node(self, node, build_mode):
        """ reevaluate the node is necessary when there is some PACKAGE_ID_UNKNOWN due to
        package_revision_mode
        """
        assert node.binary == BINARY_UNKNOWN
        output = node.conanfile.output
        node._package_id = None  # Invalidate it, so it can be re-computed
        output.info("Unknown binary for %s, computing updated ID" % str(node.ref))
        self._evaluate_package_id(node)
        output.info("Updated ID: %s" % node.package_id)
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            return
        assert node.package_id != PACKAGE_ID_UNKNOWN
        node.binary = None  # Necessary to invalidate so it is properly evaluated
        self._evaluate_node(node, build_mode)
        output.info("Binary for updated ID from: %s" % node.binary)
        if node.binary == BINARY_BUILD:
            output.info("Binary for the updated ID has to be built")
