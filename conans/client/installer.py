import os
import shutil
import textwrap
import time
from multiprocessing.pool import ThreadPool

from conan.cache.conan_reference import ConanReference
from conans.cli.output import ConanOutput
from conans.client import tools
from conans.client.conanfile.build import run_build_method
from conans.client.conanfile.package import run_package_method
from conans.client.file_copier import report_copied_files
from conans.client.generators import write_generators
from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_EDITABLE, \
    BINARY_MISSING, BINARY_SKIP, BINARY_UPDATE, BINARY_UNKNOWN, BINARY_INVALID, \
    BINARY_ERROR
from conans.client.importer import remove_imports, run_imports
from conans.client.source import retrieve_exports_sources, config_source
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter, ConanInvalidConfiguration)
from conans.model.conan_file import ConanFile
from conans.model.graph_lock import GraphLockFile
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.new_build_info import CppInfo
from conans.model.ref import PackageReference, ConanFileReference
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

    def __init__(self, cache, scoped_output, hook_manager, remote_manager):
        self._cache = cache
        self._scoped_output = scoped_output
        self._hook_manager = hook_manager
        self._remote_manager = remote_manager

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
            self._scoped_output.warning("Build folder is dirty, removing it: %s" % build_folder)
            rmdir(build_folder)
            clean_dirty(build_folder)

        if skip_build and os.path.exists(build_folder):
            self._scoped_output.info("Won't be built, using previous build folder as defined "
                                     "in build_id()")

        return build_folder, skip_build

    def _prepare_sources(self, conanfile, pref, recipe_layout, remotes):
        export_folder = recipe_layout.export()
        export_source_folder = recipe_layout.export_sources()
        scm_sources_folder = recipe_layout.scm_sources()
        conanfile_path = recipe_layout.conanfile()
        source_folder = recipe_layout.source()

        retrieve_exports_sources(self._remote_manager, recipe_layout, conanfile, pref.ref, remotes)

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_package(None)

        config_source(export_folder, export_source_folder, scm_sources_folder,
                      conanfile, conanfile_path, pref.ref,
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

        write_generators(conanfile)

        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files

        copied_files = run_imports(conanfile)

        try:
            mkdir(conanfile.build_folder)
            with tools.chdir(conanfile.build_folder):
                run_build_method(conanfile, self._hook_manager, reference=pref.ref,
                                 package_id=pref.id)
            conanfile.output.success("Package '%s' built" % pref.id)
            conanfile.output.info("Build folder %s" % conanfile.build_folder)
        except Exception as exc:
            conanfile.output.writeln("")
            conanfile.output.error("Package '%s' build failed" % pref.id)
            conanfile.output.warning("Build folder %s" % conanfile.build_folder)
            if isinstance(exc, ConanExceptionInUserConanfileMethod):
                raise exc
            raise ConanException(exc)
        finally:
            # Now remove all files that were imported with imports()
            remove_imports(conanfile, copied_files)

    def _package(self, conanfile, pref, conanfile_path):
        # FIXME: Is weak to assign here the recipe_hash
        # Creating ***info.txt files
        save(os.path.join(conanfile.folders.base_build, CONANINFO), conanfile.info.dumps())
        conanfile.output.info("Generated %s" % CONANINFO)

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

    def build_package(self, node, remotes, package_layout):
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
            conanfile.output.info('Building your package in %s' % base_build)
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
            except ConanException as exc:
                raise exc

        return node.pref


def _remove_folder_raising(folder):
    try:
        rmdir(folder)
    except OSError as e:
        raise ConanException("%s\n\nCouldn't remove folder, might be busy or open\n"
                             "Close any app using it, and retry" % str(e))


def _handle_system_requirements(conanfile, package_layout):
    """ check first the system_reqs/system_requirements.txt existence, if not existing
    check package/sha1/

    Used after remote package retrieving and before package building
    """
    # TODO: Check if this idiom should be generalize to all methods defined in base ConanFile
    # Instead of calling empty methods
    if type(conanfile).system_requirements == ConanFile.system_requirements:
        return

    system_reqs_path = package_layout.system_reqs()
    system_reqs_package_path = package_layout.system_reqs_package()

    ret = call_system_requirements(conanfile)

    try:
        ret = str(ret or "")
    except Exception:
        conanfile.out.warning("System requirements didn't return a string")
        ret = ""
    if getattr(conanfile, "global_system_requirements", None):
        save(system_reqs_path, ret)
    else:
        save(system_reqs_package_path, ret)


def call_system_requirements(conanfile):
    try:
        return conanfile.system_requirements()
    except Exception as e:
        conanfile.output.error("while executing system_requirements(): %s" % str(e))
        raise ConanException("Error in system requirements")


class BinaryInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """

    def __init__(self, app):
        self._cache = app.cache
        self._out = ConanOutput()
        self._remote_manager = app.remote_manager
        self._binaries_analyzer = app.binaries_analyzer
        self._hook_manager = app.hook_manager
        # Load custom generators from the cache, generators are part of the binary
        # build and install. Generators loaded here from the cache will have precedence
        # and overwrite possible generators loaded from packages (requires)
        for generator_path in app.cache.generators:
            app.loader.load_generators(generator_path)

    def install(self, deps_graph, remotes, build_mode, update, profile_host, profile_build,
                graph_lock):
        assert not deps_graph.error, "This graph cannot be installed: {}".format(deps_graph)
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

        conanfile.output.warning(msg)

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

        parallel = self._cache.config.parallel_download
        if parallel is not None:
            self._out.info("Downloading binary packages in %s parallel threads" % parallel)
            thread_pool = ThreadPool(parallel)
            thread_pool.map(self._download_pkg, [n for n in download_nodes])
            thread_pool.close()
            thread_pool.join()
        else:
            for node in download_nodes:
                self._download_pkg(node)

    def _download_pkg(self, node):
        self._remote_manager.get_package(node.conanfile, node.pref, node.binary_remote)

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
                ref, conanfile = node.ref, node.conanfile
                output = conanfile.output

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

                    if not node.pref.revision:
                        package_layout = self._cache.create_temp_pkg_layout(node.pref)
                    else:
                        package_layout = self._cache.get_or_create_pkg_layout(node.pref)

                    _handle_system_requirements(conanfile, package_layout)
                    self._handle_node_cache(node, processed_package_refs, remotes, package_layout)

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

        write_generators(conanfile)

        graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
        graph_lock_file.save(os.path.join(conanfile.install_folder, "conan.lock"))
        output.info("Generated conan.lock")
        copied_files = run_imports(conanfile)
        report_copied_files(copied_files, output)

    def _handle_node_cache(self, node, processed_package_references, remotes, pkg_layout):
        pref = node.pref
        assert pref.id, "Package-ID without value"
        assert pref.id != PACKAGE_ID_UNKNOWN, "Package-ID error: %s" % str(pref)
        assert pkg_layout, "The pkg_layout should be declared here"
        conanfile = node.conanfile
        output = conanfile.output

        bare_pref = PackageReference(pref.ref, pref.id)
        processed_prev = processed_package_references.get(bare_pref)
        if processed_prev is not None:  # This package-id has not been processed before
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
                        pref = self._build_package(node, remotes, pkg_layout)
                    assert node.prev, "Node PREV shouldn't be empty"
                    assert node.pref.revision, "Node PREF revision shouldn't be empty"
                    assert pref.revision is not None, "PREV for %s to be built is None" % str(pref)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    # this can happen after a re-evaluation of packageID with Package_ID_unknown
                    # TODO: cache2.0. We can't pass the layout because we don't have the prev yet
                    #  move the layout inside the get... method
                    self._download_pkg(node)
                elif node.binary == BINARY_CACHE:
                    assert node.prev, "PREV for %s is None" % str(pref)
                    output.success('Already installed!')
                    log_package_got_from_local_cache(pref)
                processed_package_references[bare_pref] = node.prev

            # at this point the package reference should be complete
            if pkg_layout.reference != pref:
                self._cache.assign_prev(pkg_layout, ConanReference(pref))

            package_folder = pkg_layout.package()
            assert os.path.isdir(package_folder), ("Package '%s' folder must exist: %s\n"
                                                   % (str(pref), package_folder))
            # Call the info method
            self._call_package_info(conanfile, package_folder, ref=pref.ref, is_editable=False)

    def _build_package(self, node, remotes, pkg_layout):
        builder = _PackageBuilder(self._cache, node.conanfile.output,
                                  self._hook_manager, self._remote_manager)
        pref = builder.build_package(node, remotes, pkg_layout)
        if node.graph_lock_node:
            node.graph_lock_node.prev = pref.revision
        return pref

    def _call_package_info(self, conanfile, package_folder, ref, is_editable):
        conanfile.folders.set_base_package(package_folder)
        conanfile.folders.set_base_source(None)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_install(None)

        conanfile.user_info = UserInfo()

        with tools.chdir(package_folder):
            with conanfile_exception_formatter(str(conanfile), "package_info"):
                self._hook_manager.execute("pre_package_info", conanfile=conanfile,
                                           reference=ref)

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

                    full_editable_cppinfo = CppInfo()
                    full_editable_cppinfo.merge(source_cppinfo)
                    full_editable_cppinfo.merge(build_cppinfo)
                    # In editables if we defined anything in the cpp infos we want to discard
                    # the one defined in the conanfile cpp_info
                    conanfile.cpp_info.merge(full_editable_cppinfo, overwrite=True)

                self._hook_manager.execute("post_package_info", conanfile=conanfile,
                                           reference=ref)
