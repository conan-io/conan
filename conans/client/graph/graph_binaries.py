import json
import os
from collections import OrderedDict

from conan.api.output import ConanOutput
from conan.internal.cache.home_paths import HomePaths
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.compatibility import BinaryCompatibility
from conans.client.graph.compute_pid import compute_package_id
from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_UPDATE, RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP,
                                       BINARY_INVALID, BINARY_EDITABLE_BUILD, RECIPE_PLATFORM,
                                       BINARY_PLATFORM)
from conans.client.graph.proxy import should_update_reference
from conans.errors import NoRemoteAvailable, NotFoundException, \
    PackageNotFoundException, conanfile_exception_formatter, ConanConnectionError, ConanException
from conans.model.info import RequirementInfo, RequirementsInfo
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load


class GraphBinariesAnalyzer(object):

    def __init__(self, conan_app, global_conf):
        self._cache = conan_app.cache
        self._home_folder = conan_app.cache_folder
        self._global_conf = global_conf
        self._remote_manager = conan_app.remote_manager
        # These are the nodes with pref (not including PREV) that have been evaluated
        self._evaluated = {}  # {pref: [nodes]}
        compat_folder = HomePaths(conan_app.cache_folder).compatibility_plugin_path
        self._compatibility = BinaryCompatibility(compat_folder)

    @staticmethod
    def _evaluate_build(node, build_mode):
        ref, conanfile = node.ref, node.conanfile
        with_deps_to_build = False
        # check dependencies, if they are being built, "cascade" will try to build this one too
        if build_mode.cascade:
            with_deps_to_build = any(dep.dst.binary in (BINARY_BUILD, BINARY_EDITABLE_BUILD)
                                     for dep in node.dependencies)
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
    def _get_package_from_remotes(self, node, remotes, update):
        results = []
        pref = node.pref
        for r in remotes:
            try:
                info = node.conanfile.info
                latest_pref = self._remote_manager.get_latest_package_reference(pref, r, info)
                results.append({'pref': latest_pref, 'remote': r})
                if len(results) > 0 and not should_update_reference(node.ref, update):
                    break
            except NotFoundException:
                pass
            except ConanConnectionError:
                ConanOutput().error(f"Failed checking for binary '{pref}' in remote '{r.name}': "
                                    "remote not available")
                raise
        if not remotes and should_update_reference(node.ref, update):
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
            node.should_build = previous_node.should_build
            node.build_allowed = previous_node.build_allowed

            # this line fixed the compatible_packages with private case.
            # https://github.com/conan-io/conan/issues/9880
            node._package_id = previous_node.package_id
            return True
        self._evaluated[pref] = [node]

    def _process_compatible_packages(self, node, remotes, update):
        conanfile = node.conanfile
        original_binary = node.binary
        original_package_id = node.package_id

        compatibles = self._compatibility.compatibles(conanfile)
        existing = compatibles.pop(original_package_id, None)   # Skip main package_id
        if existing:  # Skip the check if same package_id
            conanfile.output.debug(f"Compatible package ID {original_package_id} equal to "
                                   "the default package ID: Skipping it.")

        if not compatibles:
            return

        def _compatible_found(pkg_id, compatible_pkg):
            diff = conanfile.info.dump_diff(compatible_pkg)
            conanfile.output.success(f"Found compatible package '{pkg_id}': {diff}")
            # So they are available in package_info() method
            conanfile.info = compatible_pkg  # Redefine current

            # TODO: Improve this interface
            # The package_id method might have modified the settings to erase information,
            # ensure we allow those new values
            conanfile.settings = conanfile.settings.copy_conaninfo_settings()
            conanfile.settings.update_values(compatible_pkg.settings.values_list)
            # Trick to allow mutating the options (they were freeze=True)
            conanfile.options = conanfile.options.copy_conaninfo_options()
            conanfile.options.update_options(compatible_pkg.options)

        conanfile.output.info(f"Main binary package '{original_package_id}' missing")
        conanfile.output.info(f"Checking {len(compatibles)} compatible configurations")
        for package_id, compatible_package in compatibles.items():
            if should_update_reference(node.ref, update):
                conanfile.output.info(f"'{package_id}': "
                                      f"{conanfile.info.dump_diff(compatible_package)}")
            node._package_id = package_id  # Modifying package id under the hood, FIXME
            node.binary = None  # Invalidate it
            self._process_compatible_node(node, remotes, update)  # TODO: what if BINARY_BUILD
            if node.binary in (BINARY_CACHE, BINARY_UPDATE, BINARY_DOWNLOAD):
                _compatible_found(package_id, compatible_package)
                return
        if not should_update_reference(conanfile.ref, update):
            conanfile.output.info(f"Compatible configurations not found in cache, checking servers")
            for package_id, compatible_package in compatibles.items():
                conanfile.output.info(f"'{package_id}': "
                                      f"{conanfile.info.dump_diff(compatible_package)}")
                node._package_id = package_id  # Modifying package id under the hood, FIXME
                node.binary = None  # Invalidate it
                self._evaluate_download(node, remotes, update)
                if node.binary == BINARY_DOWNLOAD:
                    _compatible_found(package_id, compatible_package)
                    return
        # If no compatible is found, restore original state
        node.binary = original_binary
        node._package_id = original_package_id

    def _evaluate_node(self, node, build_mode, remotes, update):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.prev is None, "Node.prev should be None"

        self._process_node(node, build_mode, remotes, update)
        if node.binary == BINARY_MISSING \
                and not build_mode.should_build_missing(node.conanfile) and not node.should_build:
            self._process_compatible_packages(node, remotes, update)

        if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
            node.should_build = True
            node.build_allowed = True
            node.binary = BINARY_BUILD if not node.cant_build else BINARY_INVALID

        if node.binary == BINARY_BUILD:
            conanfile = node.conanfile
            if conanfile.vendor and not conanfile.conf.get("tools.graph:vendor", choices=("build",)):
                node.conanfile.info.invalid = f"The package '{conanfile.ref}' is a vendoring one, " \
                                              f"needs to be built from source, but it " \
                                              "didn't enable 'tools.graph:vendor=build' to compute " \
                                              "its dependencies"
                node.binary = BINARY_INVALID

    def _process_node(self, node, build_mode, remotes, update):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node):
            return

        if node.conanfile.info.invalid:
            node.binary = BINARY_INVALID
            return
        if node.recipe == RECIPE_PLATFORM:
            node.binary = BINARY_PLATFORM
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

        if node.conanfile.upload_policy == "skip":
            # Download/update shouldn't be checked in the servers if this is "skip-upload"
            # The binary can only be in cache or missing.
            if cache_latest_prev:
                node.binary = BINARY_CACHE
                node.prev = cache_latest_prev.revision
            else:
                node.binary = BINARY_MISSING
        elif cache_latest_prev is None:  # This binary does NOT exist in the cache
            self._evaluate_download(node, remotes, update)
        else:  # This binary already exists in the cache, maybe can be updated
            self._evaluate_in_cache(cache_latest_prev, node, remotes, update)

    def _process_compatible_node(self, node, remotes, update):
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

        if cache_latest_prev is not None:
            # This binary already exists in the cache, maybe can be updated
            self._evaluate_in_cache(cache_latest_prev, node, remotes, update)
        elif should_update_reference(node.ref, update):
            self._evaluate_download(node, remotes, update)

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

    def _evaluate_download(self, node, remotes, update):
        try:
            self._get_package_from_remotes(node, remotes, update)
        except NotFoundException:
            node.binary = BINARY_MISSING
        else:
            node.binary = BINARY_DOWNLOAD

    def _evaluate_in_cache(self, cache_latest_prev, node, remotes, update):
        assert cache_latest_prev.revision
        if should_update_reference(node.ref, update):
            output = node.conanfile.output
            try:
                self._get_package_from_remotes(node, remotes, update)
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
                    if cache_time > node.pref_timestamp:
                        output.info("Current package revision is newer than the remote one")
                    node.pref_timestamp = cache_time
        if not node.binary:
            node.binary = BINARY_CACHE
            node.binary_remote = None
            node.prev = cache_latest_prev.revision
            node.pref_timestamp = cache_latest_prev.timestamp
            assert node.prev, "PREV for %s is None" % str(node.pref)

    def _config_version(self):
        config_mode = self._global_conf.get("core.package_id:config_mode", default=None)
        if config_mode is None:
            return
        config_version_file = HomePaths(self._home_folder).config_version_path
        try:
            config_refs = json.loads(load(config_version_file))["config_version"]
            result = OrderedDict()
            for r in config_refs:
                try:
                    config_ref = PkgReference.loads(r)
                    req_info = RequirementInfo(config_ref.ref, config_ref.package_id, config_mode)
                except ConanException:
                    config_ref = RecipeReference.loads(r)
                    req_info = RequirementInfo(config_ref, None, config_mode)
                result[config_ref] = req_info
        except Exception as e:
            raise ConanException(f"core.package_id:config_mode defined, but error while loading "
                                 f"'{os.path.basename(config_version_file)}'"
                                 f" file in cache: {self._home_folder}: {e}")
        return RequirementsInfo(result)

    def _evaluate_package_id(self, node, config_version):
        compute_package_id(node, self._global_conf, config_version=config_version)

        # TODO: layout() execution don't need to be evaluated at GraphBuilder time.
        # it could even be delayed until installation time, but if we got enough info here for
        # package_id, we can run it
        conanfile = node.conanfile
        if hasattr(conanfile, "layout"):
            with conanfile_exception_formatter(conanfile, "layout"):
                conanfile.layout()

    def evaluate_graph(self, deps_graph, build_mode, lockfile, remotes, update, build_mode_test=None,
                       tested_graph=None):
        if tested_graph is None:
            main_mode = BuildMode(build_mode)
            test_mode = None  # Should not be used at all
            mainprefs = None
        else:
            main_mode = BuildMode(["never"])
            test_mode = BuildMode(build_mode_test)
            mainprefs = [str(n.pref) for n in tested_graph.nodes
                         if n.recipe not in (RECIPE_CONSUMER, RECIPE_VIRTUAL)]

        if main_mode.cascade:
            ConanOutput().warning("Using build-mode 'cascade' is generally inefficient and it "
                                  "shouldn't be used. Use 'package_id' and 'package_id_modes' for"
                                  "more efficient re-builds")

        def _evaluate_single(n):
            mode = main_mode if mainprefs is None or str(n.pref) in mainprefs else test_mode
            if lockfile:
                locked_prev = lockfile.resolve_prev(n)  # this is not public, should never happen
                if locked_prev:
                    self._process_locked_node(n, mode, locked_prev)
                    return
            self._evaluate_node(n, mode, remotes, update)

        levels = deps_graph.by_levels()
        config_version = self._config_version()
        for level in levels[:-1]:  # all levels but the last one, which is the single consumer
            for node in level:
                self._evaluate_package_id(node, config_version)
            # group by pref to paralelize, so evaluation is done only 1 per pref
            nodes = {}
            for node in level:
                nodes.setdefault(node.pref, []).append(node)
            # PARALLEL, this is the slow part that can query servers for packages, and compatibility
            for pref, pref_nodes in nodes.items():
                _evaluate_single(pref_nodes[0])
            # END OF PARALLEL
            # Evaluate the possible nodes with repeated "prefs" that haven't been evaluated
            for pref, pref_nodes in nodes.items():
                for n in pref_nodes[1:]:
                    _evaluate_single(n)

        # Last level is always necessarily a consumer or a virtual
        assert len(levels[-1]) == 1
        node = levels[-1][0]
        assert node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL)
        if node.path is not None:
            if node.path.endswith(".py"):
                # For .py we keep evaluating the package_id, validate(), etc
                compute_package_id(node, self._global_conf, config_version=config_version)
            # To support the ``[layout]`` in conanfile.txt
            if hasattr(node.conanfile, "layout"):
                with conanfile_exception_formatter(node.conanfile, "layout"):
                    node.conanfile.layout()

        self._skip_binaries(deps_graph)

    @staticmethod
    def _skip_binaries(graph):
        required_nodes = set()
        # Aggregate all necessary starting nodes
        required_nodes.add(graph.root)
        for node in graph.nodes:
            if node.binary in (BINARY_BUILD, BINARY_EDITABLE_BUILD, BINARY_EDITABLE):
                if not node.build_allowed:  # Only those that are forced to build, not only "missing"
                    required_nodes.add(node)

        root_nodes = required_nodes.copy()
        while root_nodes:
            new_root_nodes = set()
            for node in root_nodes:
                # The nodes that are directly required by this one to build correctly
                is_consumer = not (node.recipe != RECIPE_CONSUMER and
                                   node.binary not in (BINARY_BUILD, BINARY_EDITABLE_BUILD,
                                                       BINARY_EDITABLE))
                deps_required = set(d.node for d in node.transitive_deps.values() if d.require.files
                                    or (d.require.direct and is_consumer))

                # second pass, transitive affected. Packages that have some dependency that is required
                # cannot be skipped either. In theory the binary could be skipped, but build system
                # integrations like CMakeDeps rely on find_package() to correctly find transitive deps
                indirect = (d.node for d in node.transitive_deps.values()
                            if any(t.node in deps_required for t in d.node.transitive_deps.values()))
                deps_required.update(indirect)

                # Third pass, mark requires as skippeable
                for dep in node.transitive_deps.values():
                    dep.require.skip = dep.node not in deps_required

                # Finally accumulate all needed nodes for marking binaries as SKIP download
                news_req = [r for r in deps_required
                            if r.binary in (BINARY_BUILD, BINARY_EDITABLE_BUILD, BINARY_EDITABLE)
                            if r not in required_nodes]  # Avoid already expanded before
                new_root_nodes.update(news_req)  # For expanding the next iteration
                required_nodes.update(deps_required)

            root_nodes = new_root_nodes

        for node in graph.nodes:
            if node not in required_nodes and node.conanfile.conf.get("tools.graph:skip_binaries",
                                                                      check_type=bool, default=True):
                node.binary = BINARY_SKIP
