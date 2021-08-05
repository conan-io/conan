import os
import shutil
import textwrap
import time
from multiprocessing.pool import ThreadPool

from conan.cache.conan_reference import ConanReference
from conans.client import tools
from conans.client.conanfile.build import run_build_method
from conans.client.conanfile.package import run_package_method
from conans.client.file_copier import report_copied_files
from conans.client.generators import write_toolchain
from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_EDITABLE, \
    BINARY_MISSING, BINARY_SKIP, BINARY_UPDATE, BINARY_UNKNOWN, CONTEXT_HOST, BINARY_INVALID, \
    BINARY_ERROR
from conans.client.importer import remove_imports, run_imports
from conans.client.recorder.action_recorder import INSTALL_ERROR_BUILDING, INSTALL_ERROR_MISSING
from conans.client.source import retrieve_exports_sources, config_source
from conans.client.tools import chdir
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter, ConanInvalidConfiguration)
from conans.model.build_info import CppInfo, DepCppInfo, CppInfoDefaultValues
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvInfo
from conans.model.graph_lock import GraphLockFile
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.new_build_info import NewCppInfo, fill_old_cppinfo
from conans.model.ref import PackageReference, ConanFileReference
from conans.model.user_info import DepsUserInfo
from conans.model.user_info import UserInfo
from conans.paths import CONANINFO, RUN_LOG_NAME
from conans.util.env_reader import get_env
from conans.util.files import clean_dirty, is_dirty, make_read_only, mkdir, rmdir, save, set_dirty
from conans.util.log import logger
from conans.util.tracer import log_package_built, log_package_got_from_local_cache


def build_id(conan_file):
    if hasattr(conan_file, "build_id"):
        # construct new ConanInfo
        build_id_info = conan_file.info.copy()
        conan_file.info_build = build_id_info
        # effectively call the user function to change the package values
        with conanfile_exception_formatter(str(conan_file), "build_id"):
            conan_file.build_id()
        # compute modified ID
        return build_id_info.package_id()
    return None


class _PackageBuilder(object):
    def __init__(self, cache, output, hook_manager, remote_manager, generators):
        self._cache = cache
        self._output = output
        self._hook_manager = hook_manager
        self._remote_manager = remote_manager
        self._generator_manager = generators

    def _get_build_folder(self, conanfile, package_layout):
        # Build folder can use a different package_ID if build_id() is defined.
        # This function decides if the build folder should be re-used (not build again)
        # and returns the build folder
        skip_build = False
        build_folder = package_layout.build()
        recipe_build_id = build_id(conanfile)
        pref = package_layout.reference
        if pref.id != recipe_build_id and hasattr(conanfile, "build_id"):
            # check if we already have a package with the calculated build_id
            recipe_ref = ConanFileReference.loads(ConanReference(pref).recipe_reference)
            package_ids = self._cache.get_package_ids(recipe_ref)
            build_prev = None
            for pkg_id in package_ids:
                prev = self._cache.get_latest_prev(pkg_id)
                prev_build_id = self._cache.get_build_id(prev)
                if prev_build_id == recipe_build_id:
                    build_prev = prev
                    break

            build_prev = build_prev or pref

            # We are trying to build a package id different from the one that has the
            # build_folder but belongs to the same recipe revision, so reuse the build_folder
            # from the one that is already build
            if build_prev.id != pref.id:
                other_pkg_layout = self._cache.pkg_layout(build_prev)
                build_folder = other_pkg_layout.build()
                skip_build = True
            elif build_prev == pref:
                self._cache.update_reference(build_prev, new_build_id=recipe_build_id)

        if is_dirty(build_folder):
            self._output.warn("Build folder is dirty, removing it: %s" % build_folder)
            rmdir(build_folder)
            clean_dirty(build_folder)

        if skip_build and os.path.exists(build_folder):
            self._output.info("Won't be built, using previous build folder as defined in build_id()")

        return build_folder, skip_build

    def _prepare_sources(self, conanfile, pref, recipe_layout, remotes):
        export_folder = recipe_layout.export()
        export_source_folder = recipe_layout.export_sources()
        scm_sources_folder = recipe_layout.scm_sources()
        conanfile_path = recipe_layout.conanfile()
        source_folder = recipe_layout.source()

        retrieve_exports_sources(self._remote_manager, self._cache, recipe_layout, conanfile,
                                 pref.ref, remotes)

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_package(None)

        config_source(export_folder, export_source_folder, scm_sources_folder,
                      conanfile, self._output, conanfile_path, pref.ref,
                      self._hook_manager, self._cache)

    @staticmethod
    def _copy_sources(conanfile, source_folder, build_folder):
        # Copies the sources to the build-folder, unless no_copy_source is defined
        _remove_folder_raising(build_folder)
        if not getattr(conanfile, 'no_copy_source', False):
            conanfile.output.info('Copying sources to build folder')
            try:
                shutil.copytree(source_folder, build_folder, symlinks=True)
            except Exception as e:
                msg = str(e)
                if "206" in msg:  # System error shutil.Error 206: Filename or extension too long
                    msg += "\nUse short_paths=True if paths too long"
                raise ConanException("%s\nError copying sources to build folder" % msg)
            logger.debug("BUILD: Copied to %s", build_folder)
            logger.debug("BUILD: Files copied %s", ",".join(os.listdir(build_folder)))

    def _build(self, conanfile, pref):
        # Read generators from conanfile and generate the needed files
        logger.info("GENERATORS: Writing generators")
        self._generator_manager.write_generators(conanfile, conanfile.build_folder,
                                                 conanfile.generators_folder, self._output)

        logger.info("TOOLCHAIN: Writing toolchain")
        write_toolchain(conanfile, conanfile.generators_folder, self._output)

        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files

        copied_files = run_imports(conanfile)

        try:
            mkdir(conanfile.build_folder)
            with tools.chdir(conanfile.build_folder):
                run_build_method(conanfile, self._hook_manager, reference=pref.ref,
                                 package_id=pref.id)
            self._output.success("Package '%s' built" % pref.id)
            self._output.info("Build folder %s" % conanfile.build_folder)
        except Exception as exc:
            self._output.writeln("")
            self._output.error("Package '%s' build failed" % pref.id)
            self._output.warn("Build folder %s" % conanfile.build_folder)
            if isinstance(exc, ConanExceptionInUserConanfileMethod):
                raise exc
            raise ConanException(exc)
        finally:
            # Now remove all files that were imported with imports()
            remove_imports(conanfile, copied_files, self._output)

    def _package(self, conanfile, pref, conanfile_path):
        # FIXME: Is weak to assign here the recipe_hash
        # Creating ***info.txt files
        save(os.path.join(conanfile.folders.base_build, CONANINFO), conanfile.info.dumps())
        self._output.info("Generated %s" % CONANINFO)

        package_id = pref.id
        # Do the actual copy, call the conanfile.package() method
        # While installing, the infos goes to build folder
        conanfile.folders.set_base_install(conanfile.folders.base_build)

        prev = run_package_method(conanfile, package_id, self._hook_manager, conanfile_path,
                                  pref.ref)

        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(conanfile.folders.base_package)
        # FIXME: Conan 2.0 Clear the registry entry (package ref)
        return prev

    def build_package(self, node, recorder, remotes, package_layout):
        t1 = time.time()

        conanfile = node.conanfile
        pref = node.pref

        # TODO: cache2.0 fix this
        recipe_layout = self._cache.ref_layout(pref.ref)

        base_source = recipe_layout.source()
        conanfile_path = recipe_layout.conanfile()
        base_package = package_layout.package()

        base_build, skip_build = self._get_build_folder(conanfile, package_layout)

        # PREPARE SOURCES
        if not skip_build:
            # TODO: cache2.0 check locks
            # with package_layout.conanfile_write_lock(self._output):
            set_dirty(base_build)
            self._prepare_sources(conanfile, pref, recipe_layout, remotes)
            self._copy_sources(conanfile, base_source, base_build)
            mkdir(base_build)

        # BUILD & PACKAGE
        # TODO: cache2.0 check locks
        # with package_layout.conanfile_read_lock(self._output):
        with tools.chdir(base_build):
            self._output.info('Building your package in %s' % base_build)
            try:
                if getattr(conanfile, 'no_copy_source', False):
                    conanfile.folders.set_base_source(base_source)
                else:
                    conanfile.folders.set_base_source(base_build)

                conanfile.folders.set_base_build(base_build)
                conanfile.folders.set_base_imports(base_build)
                conanfile.folders.set_base_package(base_package)

                if not skip_build:
                    # In local cache, generators folder always in build_folder
                    conanfile.folders.set_base_generators(base_build)
                    # In local cache, install folder always is build_folder
                    conanfile.folders.set_base_install(base_build)
                    self._build(conanfile, pref)
                    clean_dirty(base_build)

                prev = self._package(conanfile, pref, conanfile_path)
                assert prev
                node.prev = prev
                log_file = os.path.join(base_build, RUN_LOG_NAME)
                log_file = log_file if os.path.exists(log_file) else None
                log_package_built(pref, time.time() - t1, log_file)
                recorder.package_built(pref)
            except ConanException as exc:
                recorder.package_install_error(pref, INSTALL_ERROR_BUILDING, str(exc),
                                               remote_name=None)
                raise exc

        return node.pref


def _remove_folder_raising(folder):
    try:
        rmdir(folder)
    except OSError as e:
        raise ConanException("%s\n\nCouldn't remove folder, might be busy or open\n"
                             "Close any app using it, and retry" % str(e))


def _handle_system_requirements(conan_file, package_layout, out):
    """ check first the system_reqs/system_requirements.txt existence, if not existing
    check package/sha1/

    Used after remote package retrieving and before package building
    """
    # TODO: Check if this idiom should be generalize to all methods defined in base ConanFile
    # Instead of calling empty methods
    if type(conan_file).system_requirements == ConanFile.system_requirements:
        return

    system_reqs_path = package_layout.system_reqs()
    system_reqs_package_path = package_layout.system_reqs_package()

    ret = call_system_requirements(conan_file, out)

    try:
        ret = str(ret or "")
    except Exception:
        out.warn("System requirements didn't return a string")
        ret = ""
    if getattr(conan_file, "global_system_requirements", None):
        save(system_reqs_path, ret)
    else:
        save(system_reqs_package_path, ret)


def call_system_requirements(conanfile, output):
    try:
        return conanfile.system_requirements()
    except Exception as e:
        output.error("while executing system_requirements(): %s" % str(e))
        raise ConanException("Error in system requirements")


class BinaryInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """

    def __init__(self, app, recorder):
        self._cache = app.cache
        self._out = app.out
        self._remote_manager = app.remote_manager
        self._recorder = recorder
        self._binaries_analyzer = app.binaries_analyzer
        self._hook_manager = app.hook_manager
        self._generator_manager = app.generator_manager
        # Load custom generators from the cache, generators are part of the binary
        # build and install. Generators loaded here from the cache will have precedence
        # and overwrite possible generators loaded from packages (requires)
        for generator_path in app.cache.generators:
            app.loader.load_generators(generator_path)

    def install(self, deps_graph, remotes, build_mode, update, profile_host, profile_build,
                graph_lock):
        # order by levels and separate the root node (ref=None) from the rest
        nodes_by_level = deps_graph.by_levels()
        root_level = nodes_by_level.pop()
        root_node = root_level[0]
        # Get the nodes in order and if we have to build them
        self._out.info("Installing (downloading, building) binaries...")
        self._build(nodes_by_level, root_node, profile_host, profile_build,
                    graph_lock, remotes, build_mode, update)

    @staticmethod
    def _classify(nodes_by_level):
        missing, invalid, downloads = [], [], []
        for level in nodes_by_level:
            for node in level:
                if node.binary == BINARY_MISSING:
                    missing.append(node)
                elif node.binary in (BINARY_INVALID, BINARY_ERROR):
                    invalid.append(node)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    downloads.append(node)
        return missing, invalid, downloads

    def _raise_missing(self, missing):
        if not missing:
            return

        missing_prefs = set(n.pref for n in missing)  # avoid duplicated
        missing_prefs = list(sorted(missing_prefs))
        for pref in missing_prefs:
            self._out.error("Missing binary: %s" % str(pref))
        self._out.writeln("")

        # Report details just the first one
        node = missing[0]
        package_id = node.package_id
        ref, conanfile = node.ref, node.conanfile
        dependencies = [str(dep.dst) for dep in node.dependencies]

        settings_text = ", ".join(conanfile.info.full_settings.dumps().splitlines())
        options_text = ", ".join(conanfile.info.full_options.dumps().splitlines())
        dependencies_text = ', '.join(dependencies)
        requires_text = ", ".join(conanfile.info.requires.dumps().splitlines())

        msg = textwrap.dedent('''\
            Can't find a '%s' package for the specified settings, options and dependencies:
            - Settings: %s
            - Options: %s
            - Dependencies: %s
            - Requirements: %s
            - Package ID: %s
            ''' % (ref, settings_text, options_text, dependencies_text, requires_text, package_id))
        conanfile.output.warn(msg)
        self._recorder.package_install_error(PackageReference(ref, package_id),
                                             INSTALL_ERROR_MISSING, msg)
        missing_pkgs = "', '".join([str(pref.ref) for pref in missing_prefs])
        if len(missing_prefs) >= 5:
            build_str = "--build=missing"
        else:
            build_str = " ".join(["--build=%s" % pref.ref.name for pref in missing_prefs])

        raise ConanException(textwrap.dedent('''\
            Missing prebuilt package for '%s'
            Try to build from sources with '%s'
            Use 'conan search <reference> --table table.html'
            Or read 'http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package'
            ''' % (missing_pkgs, build_str)))

    def _download(self, downloads, processed_package_refs):
        """ executes the download of packages (both download and update), only once for a given
        PREF, even if node duplicated
        :param downloads: all nodes to be downloaded or updated, included repetitions
        """
        if not downloads:
            return

        download_nodes = []
        for node in downloads:
            pref = node.pref
            bare_pref = PackageReference(pref.ref, pref.id)
            if bare_pref in processed_package_refs:
                continue
            processed_package_refs[bare_pref] = pref.revision
            assert node.prev, "PREV for %s is None" % str(node.pref)
            download_nodes.append(node)

        def _download(n):
            # We cannot embed the package_lock inside the remote.get_package()
            # because the handle_node_cache has its own lock
            # TODO: cache2.0 check locks
            pkg_layout = self._cache.pkg_layout(n.pref)
            with pkg_layout.package_lock():
                self._download_pkg(n)

        parallel = self._cache.config.parallel_download
        if parallel is not None:
            self._out.info("Downloading binary packages in %s parallel threads" % parallel)
            thread_pool = ThreadPool(parallel)
            thread_pool.map(_download, [n for n in download_nodes])
            thread_pool.close()
            thread_pool.join()
        else:
            for node in download_nodes:
                _download(node)

    def _download_pkg(self, node):
        return self._remote_manager.get_package(node.conanfile, node.pref, node.binary_remote,
                                                node.conanfile.output, self._recorder)

    def _build(self, nodes_by_level, root_node, profile_host, profile_build, graph_lock,
               remotes, build_mode, update):
        missing, invalid, downloads = self._classify(nodes_by_level)
        if invalid:
            msg = ["There are invalid packages (packages that cannot exist for this configuration):"]
            for node in invalid:
                binary, reason = node.conanfile.info.invalid
                msg.append("{}: {}: {}".format(node.conanfile, binary, reason))
            raise ConanInvalidConfiguration("\n".join(msg))
        self._raise_missing(missing)
        processed_package_refs = {}
        self._download(downloads, processed_package_refs)

        for level in nodes_by_level:
            for node in level:
                ref, conan_file = node.ref, node.conanfile
                output = conan_file.output

                self._propagate_info(node)
                if node.binary == BINARY_EDITABLE:
                    self._handle_node_editable(node, profile_host, profile_build, graph_lock)
                    # Need a temporary package revision for package_revision_mode
                    # Cannot be PREV_UNKNOWN otherwise the consumers can't compute their packageID
                    node.prev = "editable"
                else:
                    if node.binary == BINARY_SKIP:  # Privates not necessary
                        continue
                    assert ref.revision is not None, "Installer should receive RREV always"
                    if node.binary == BINARY_UNKNOWN:
                        self._binaries_analyzer.reevaluate_node(node, remotes, build_mode, update)
                        if node.binary == BINARY_MISSING:
                            self._raise_missing([node])

                    package_layout = self._cache.create_temp_pkg_layout(node.pref) if \
                        not node.pref.revision else self._cache.pkg_layout(node.pref)

                    _handle_system_requirements(conan_file, package_layout, output)
                    self._handle_node_cache(node, processed_package_refs, remotes, package_layout)

        # Finally, propagate information to root node (ref=None)
        self._propagate_info(root_node)

    def _handle_node_editable(self, node, profile_host, profile_build, graph_lock):
        # Get source of information
        conanfile = node.conanfile
        ref = node.ref
        conanfile_path = self._cache.editable_path(ref)
        # TODO: Check, this assumes the folder is always the conanfile one
        base_path = os.path.dirname(conanfile_path)
        self._call_package_info(conanfile, package_folder=base_path, ref=ref, is_editable=True)

        # New editables mechanism based on Folders
        conanfile.folders.set_base_package(base_path)
        conanfile.folders.set_base_source(base_path)
        conanfile.folders.set_base_build(base_path)
        conanfile.folders.set_base_install(base_path)
        conanfile.folders.set_base_imports(base_path)

        output = conanfile.output
        output.info("Rewriting files of editable package "
                    "'{}' at '{}'".format(conanfile.name, conanfile.generators_folder))
        self._generator_manager.write_generators(conanfile, conanfile.install_folder,
                                                 conanfile.generators_folder, output)
        write_toolchain(conanfile, conanfile.generators_folder, output)
        output.info("Generated toolchain")
        graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
        graph_lock_file.save(os.path.join(conanfile.install_folder, "conan.lock"))
        output.info("Generated conan.lock")
        copied_files = run_imports(conanfile)
        report_copied_files(copied_files, output)

    def _handle_node_cache(self, node, processed_package_references, remotes, pkg_layout):
        pref = node.pref
        assert pref.id, "Package-ID without value"
        assert pref.id != PACKAGE_ID_UNKNOWN, "Package-ID error: %s" % str(pref)
        conanfile = node.conanfile
        output = conanfile.output

        bare_pref = PackageReference(pref.ref, pref.id)
        processed_prev = processed_package_references.get(bare_pref)
        if processed_prev is None:  # This package-id has not been processed before
            if not pkg_layout:
                if pref.revision:
                    raise ConanException("should this happen?")
                    pkg_layout = self._cache.pkg_layout(pref)
                else:
                    pkg_layout = self._cache.create_temp_pkg_layout(pref)
        else:
            # We need to update the PREV of this node, as its processing has been skipped,
            # but it could be that another node with same PREF was built and obtained a new PREV
            node.prev = processed_prev
            pref = pref.copy_with_revs(pref.ref.revision, processed_prev)
            pkg_layout = self._cache.pkg_layout(pref)

        with pkg_layout.package_lock():
            if processed_prev is None:  # This package-id has not been processed before
                if node.binary == BINARY_BUILD:
                    assert node.prev is None, "PREV for %s to be built should be None" % str(pref)
                    pkg_layout.package_remove()
                    with pkg_layout.set_dirty_context_manager():
                        pref = self._build_package(node, output, remotes, pkg_layout)
                    self._call_post_package(node, output, pkg_layout)
                    assert node.prev, "Node PREV shouldn't be empty"
                    assert node.pref.revision, "Node PREF revision shouldn't be empty"
                    assert pref.revision is not None, "PREV for %s to be built is None" % str(pref)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    # this can happen after a re-evaluation of packageID with Package_ID_unknown
                    # TODO: cache2.0. We can't pass the layout because we don't have the prev yet
                    #  move the layout inside the get... method
                    pkg_layout = self._download_pkg(node)
                    self._call_post_package(node, output, pkg_layout)
                elif node.binary == BINARY_CACHE:
                    assert node.prev, "PREV for %s is None" % str(pref)
                    output.success('Already installed!')
                    log_package_got_from_local_cache(pref)
                    self._recorder.package_fetched_from_cache(pref)
                processed_package_references[bare_pref] = node.prev

            # at this point the package reference should be complete
            if pkg_layout.reference != pref:
                self._cache.assign_prev(pkg_layout, ConanReference(pref))

            if os.path.exists(pkg_layout.post_package()):
                output.info('Using package install folder')
                package_folder = pkg_layout.post_package()
            else:
                package_folder = pkg_layout.package()
            assert os.path.isdir(package_folder), ("Package '%s' folder must exist: %s\n"
                                                   % (str(pref), package_folder))
            # Call the info method
            self._call_package_info(conanfile, package_folder, ref=pref.ref, is_editable=False)
            self._recorder.package_cpp_info(pref, conanfile.cpp_info)

    def _call_post_package(self, node, output, pkg_layout):
        conanfile = node.conanfile
        # FIXME: better name? "install" might be confusing with the old install_folder mechanism
        # FIXME: Maybe it is better to remove first the install folder here in develop2
        # TODO: dirty?
        if hasattr(conanfile, "post_package") and callable(getattr(conanfile, "post_package")):
            shutil.copytree(pkg_layout.package(), pkg_layout.post_package(), symlinks=True)
            with chdir(pkg_layout.package()):
                conanfile.folders.set_base_post_package(pkg_layout.post_package())
                output.info("Calling post_package() method...")
                conanfile.post_package()

    def _build_package(self, node, output, remotes, pkg_layout):
        conanfile = node.conanfile
        # It is necessary to complete the sources of python requires, which might be used
        # Only the legacy python_requires allow this
        python_requires = getattr(conanfile, "python_requires", None)
        if python_requires and isinstance(python_requires, dict):  # Old legacy python_requires
            for python_require in python_requires.values():
                assert python_require.ref.revision is not None, \
                    "Installer should receive python_require.ref always"
                retrieve_exports_sources(self._remote_manager, self._cache, pkg_layout,
                                         python_require.conanfile, python_require.ref, remotes)

        builder = _PackageBuilder(self._cache, output, self._hook_manager, self._remote_manager,
                                  self._generator_manager)
        pref = builder.build_package(node, self._recorder, remotes, pkg_layout)
        if node.graph_lock_node:
            node.graph_lock_node.prev = pref.revision
        return pref

    def _propagate_info(self, node):
        # it is necessary to recompute
        # the node transitive information necessary to compute the package_id
        # as it will be used by reevaluate_node() when package_revision_mode is used and
        # PACKAGE_ID_UNKNOWN happens due to unknown revisions
        self._binaries_analyzer.package_id_transitive_reqs(node)
        # Get deps_cpp_info from upstream nodes
        node_order = [n for n in node.public_closure if n.binary != BINARY_SKIP]
        # List sort is stable, will keep the original order of the closure, but prioritize levels
        conan_file = node.conanfile
        transitive = [it for it in node.transitive_closure.values()]

        br_host = []
        for it in node.dependencies:
            if it.require.build_require_context == CONTEXT_HOST:
                br_host.extend(it.dst.transitive_closure.values())

        # Initialize some members if we are using different contexts
        conan_file.user_info_build = DepsUserInfo()

        for n in node_order:
            if n not in transitive:
                conan_file.output.info("Applying build-requirement: %s" % str(n.ref))

            dep_cpp_info = n.conanfile._conan_dep_cpp_info

            # The new build/host propagation model
            if n in transitive or n in br_host:
                conan_file.deps_user_info[n.ref.name] = n.conanfile.user_info
                conan_file.deps_cpp_info.add(n.ref.name, dep_cpp_info)
            else:
                conan_file.user_info_build[n.ref.name] = n.conanfile.user_info
                env_info = EnvInfo()
                env_info._values_ = n.conanfile.env_info._values_.copy()
                # Add cpp_info.bin_paths/lib_paths to env_info (it is needed for runtime)
                env_info.DYLD_LIBRARY_PATH.extend(dep_cpp_info.lib_paths)
                env_info.DYLD_FRAMEWORK_PATH.extend(dep_cpp_info.framework_paths)
                env_info.LD_LIBRARY_PATH.extend(dep_cpp_info.lib_paths)
                env_info.PATH.extend(dep_cpp_info.bin_paths)
                conan_file.deps_env_info.update(env_info, n.ref.name)

    def _call_package_info(self, conanfile, package_folder, ref, is_editable):
        conanfile.cpp_info = CppInfo(conanfile.name, package_folder)
        conanfile.cpp_info.version = conanfile.version
        conanfile.cpp_info.description = conanfile.description

        conanfile.folders.set_base_package(package_folder)
        conanfile.folders.set_base_source(None)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_install(None)

        conanfile.env_info = EnvInfo()
        conanfile.user_info = UserInfo()

        # Get deps_cpp_info from upstream nodes
        public_deps = [name for name, req in conanfile.requires.items() if not req.private
                       and not req.override]
        conanfile.cpp_info.public_deps = public_deps
        # Once the node is build, execute package info, so it has access to the
        # package folder and artifacts

        with tools.chdir(package_folder):
            with conanfile_exception_formatter(str(conanfile), "package_info"):
                self._hook_manager.execute("pre_package_info", conanfile=conanfile,
                                           reference=ref)
                if hasattr(conanfile, "layout"):
                    # Old cpp info without defaults (the defaults are in the new one)
                    conanfile.cpp_info = CppInfo(conanfile.name, package_folder,
                                                 default_values=CppInfoDefaultValues())
                    if not is_editable:
                        package_cppinfo = conanfile.cpp.package.copy()
                        package_cppinfo.set_relative_base_folder(conanfile.folders.package)
                        # Copy the infos.package into the old cppinfo
                        fill_old_cppinfo(conanfile.cpp.package, conanfile.cpp_info)
                    else:
                        conanfile.cpp_info.filter_empty = False

                conanfile.package_info()

                if hasattr(conanfile, "layout") and is_editable:
                    # Adjust the folders of the layout to consolidate the rootfolder of the
                    # cppinfos inside
                    conanfile.folders.set_base_build(package_folder)
                    conanfile.folders.set_base_source(package_folder)
                    conanfile.folders.set_base_generators(package_folder)

                    # convert directory entries to be relative to the declared folders.build
                    build_cppinfo = conanfile.cpp.build.copy()
                    build_cppinfo.set_relative_base_folder(conanfile.folders.build)

                    # convert directory entries to be relative to the declared folders.source
                    source_cppinfo = conanfile.cpp.source.copy()
                    source_cppinfo.set_relative_base_folder(conanfile.folders.source)

                    full_editable_cppinfo = NewCppInfo()
                    full_editable_cppinfo.merge(source_cppinfo)
                    full_editable_cppinfo.merge(build_cppinfo)
                    # Paste the editable cpp_info but prioritizing it, only if a
                    # variable is not declared at build/source, the package will keep the value
                    fill_old_cppinfo(full_editable_cppinfo, conanfile.cpp_info)

                if conanfile._conan_dep_cpp_info is None:
                    try:
                        if not is_editable:
                            # FIXME: The default for the cppinfo from build are not the same
                            #        so this check fails when editable
                            conanfile.cpp_info._raise_incorrect_components_definition(
                                conanfile.name, conanfile.requires)
                    except ConanException as e:
                        raise ConanException("%s package_info(): %s" % (str(conanfile), e))
                    conanfile._conan_dep_cpp_info = DepCppInfo(conanfile.cpp_info)
                self._hook_manager.execute("post_package_info", conanfile=conanfile,
                                           reference=ref)
