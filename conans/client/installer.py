import os
import shutil
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
    BINARY_MISSING, BINARY_UPDATE, BINARY_UNKNOWN
from conans.client.graph.install_graph import InstallGraph, raise_missing
from conans.client.importer import remove_imports, run_imports
from conans.client.source import retrieve_exports_sources, config_source
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.package_ref import PkgReference
from conans.model.ref import ConanFileReference
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

    def __init__(self, app, scoped_output):
        self._app = app
        self._cache = app.cache
        self._scoped_output = scoped_output
        self._hook_manager = app.hook_manager
        self._remote_manager = app.remote_manager

    def _get_build_folder(self, conanfile, package_layout):
        # Build folder can use a different package_ID if build_id() is defined.
        # This function decides if the build folder should be re-used (not build again)
        # and returns the build folder
        skip_build = False
        build_folder = package_layout.build()
        recipe_build_id = build_id(conanfile)
        pref = package_layout.reference
        if recipe_build_id is not None and pref.package_id != recipe_build_id:
            package_layout.build_id = recipe_build_id
            # check if we already have a package with the calculated build_id
            recipe_ref = ConanFileReference.loads(ConanReference(pref).recipe_reference)
            package_refs = self._cache.get_package_references(recipe_ref)
            build_prev = None
            for _pkg_ref in package_refs:
                prev = self._cache.get_latest_prev(_pkg_ref)
                prev_build_id = self._cache.get_build_id(prev)
                if prev_build_id == recipe_build_id:
                    build_prev = prev
                    break

            build_prev = build_prev or pref

            # We are trying to build a package id different from the one that has the
            # build_folder but belongs to the same recipe revision, so reuse the build_folder
            # from the one that is already build
            if build_prev.package_id != pref.package_id:
                other_pkg_layout = self._cache.pkg_layout(build_prev)
                build_folder = other_pkg_layout.build()
                skip_build = True

        if is_dirty(build_folder):
            self._scoped_output.warning("Build folder is dirty, removing it: %s" % build_folder)
            rmdir(build_folder)
            clean_dirty(build_folder)

        if skip_build and os.path.exists(build_folder):
            self._scoped_output.info("Won't be built, using previous build folder as defined "
                                     "in build_id()")

        return build_folder, skip_build

    def _prepare_sources(self, conanfile, pref, recipe_layout):
        export_folder = recipe_layout.export()
        export_source_folder = recipe_layout.export_sources()
        scm_sources_folder = recipe_layout.scm_sources()
        conanfile_path = recipe_layout.conanfile()
        source_folder = recipe_layout.source()

        remotes = self._app.enabled_remotes
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
                                 package_id=pref.package_id)
            conanfile.output.success("Package '%s' built" % pref.package_id)
            conanfile.output.info("Build folder %s" % conanfile.build_folder)
        except Exception as exc:
            conanfile.output.writeln("")
            conanfile.output.error("Package '%s' build failed" % pref.package_id)
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

        package_id = pref.package_id
        # Do the actual copy, call the conanfile.package() method
        # While installing, the infos goes to build folder
        conanfile.folders.set_base_install(conanfile.folders.base_build)

        prev = run_package_method(conanfile, package_id, self._hook_manager, conanfile_path,
                                  pref.ref)

        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(conanfile.folders.base_package)
        # FIXME: Conan 2.0 Clear the registry entry (package ref)
        return prev

    def build_package(self, node, package_layout):
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
            self._prepare_sources(conanfile, pref, recipe_layout)
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


def _handle_system_requirements(install_node, package_layout):
    """ check first the system_reqs/system_requirements.txt existence, if not existing
    check package/sha1/

    Used after remote package retrieving and before package building
    """
    node = install_node.nodes[0]
    conanfile = node.conanfile
    # TODO: Check if this idiom should be generalize to all methods defined in base ConanFile
    # Instead of calling empty methods
    if type(conanfile).system_requirements == ConanFile.system_requirements:
        return

    system_reqs_path = package_layout.system_reqs()
    system_reqs_package_path = package_layout.system_reqs_package()

    ret = call_system_requirements(conanfile)
    ret = str(ret or "")
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
        self._app = app
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

    def install(self, deps_graph, build_mode):
        assert not deps_graph.error, "This graph cannot be installed: {}".format(deps_graph)

        self._out.info("\nInstalling (downloading, building) binaries...")

        # order by levels and separate the root node (ref=None) from the rest
        install_graph = InstallGraph(deps_graph)
        install_graph.raise_errors(self._out)
        install_order = install_graph.install_order()

        self._download_bulk(install_order)
        for level in install_order:
            for install_reference in level:
                for package in install_reference.packages:
                    self._handle_package(package, install_reference, build_mode)

    def _download_bulk(self, install_order):
        """ executes the download of packages (both download and update), only once for a given
        PREF
        """
        downloads = []
        for level in install_order:
            for node in level:
                for package in node.packages:
                    if package.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                        downloads.append(package)
        if not downloads:
            return
        parallel = self._cache.config.parallel_download
        if parallel is not None:
            self._out.info("Downloading binary packages in %s parallel threads" % parallel)
            thread_pool = ThreadPool(parallel)
            thread_pool.map(self._download_pkg, downloads)
            thread_pool.close()
            thread_pool.join()
        else:
            for node in downloads:
                self._download_pkg(node)

    def _download_pkg(self, package):
        node = package.nodes[0]
        assert node.pref.revision is not None
        self._remote_manager.get_package(node.conanfile, node.pref, node.binary_remote)

    def _handle_package(self, package, install_reference, build_mode):
        if package.binary == BINARY_EDITABLE:
            self._handle_node_editable(package)
            return

        assert package.binary in (BINARY_CACHE, BINARY_BUILD, BINARY_UNKNOWN, BINARY_DOWNLOAD,
                                  BINARY_UPDATE)
        assert install_reference.ref.revision is not None, "Installer should receive RREV always"
        not_processed = True
        if package.binary == BINARY_UNKNOWN:
            assert len(package.nodes) == 1, "PACKAGE_ID_UNKNOWN are not the same"
            node = package.nodes[0]
            self._binaries_analyzer.reevaluate_node(node, build_mode)
            package.package_id = node.pref.package_id  # Just in case it was recomputed
            package.prev = node.pref.revision
            package.binary = node.binary
            not_processed = install_reference.update_unknown(package)
            if not_processed:
                # The new computed package_id has not been processed yet
                if node.binary == BINARY_MISSING:
                    raise_missing([package], self._out)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    self._download_pkg(package)

        pref = PkgReference(install_reference.ref, package.package_id, package.prev)
        if pref.revision is None:
            assert package.binary == BINARY_BUILD
            package_layout = self._cache.create_temp_pkg_layout(pref)
        else:
            package_layout = self._cache.get_or_create_pkg_layout(pref)

        if not_processed:
            _handle_system_requirements(package, package_layout)

            if package.binary == BINARY_BUILD:
                self._handle_node_build(package, package_layout)
                # Just in case it was recomputed
                package.package_id = package.nodes[0].pref.package_id  # Just in case it was recomputed
                package.prev = package.nodes[0].pref.revision
                package.binary = package.nodes[0].binary
                pref = PkgReference(install_reference.ref, package.package_id, package.prev)
            elif package.binary == BINARY_CACHE:
                node = package.nodes[0]
                pref = node.pref
                assert node.prev, "PREV for %s is None" % str(pref)
                output = node.conanfile.output
                output.success('Already installed!')
                log_package_got_from_local_cache(pref)

        # Make sure that all nodes with same pref compute package_info()
        pkg_folder = package_layout.package()
        assert os.path.isdir(pkg_folder), \
            "Package '%s' folder must exist: %s" % (str(pref), pkg_folder)
        for n in package.nodes:
            n.prev = pref.revision  # Make sure the prev is assigned
            conanfile = n.conanfile
            # Call the info method
            self._call_package_info(conanfile, pkg_folder, ref=pref.ref, is_editable=False)

    def _handle_node_editable(self, install_node):
        for node in install_node.nodes:
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

            # Need a temporary package revision for package_revision_mode
            # Cannot be PREV_UNKNOWN otherwise the consumers can't compute their packageID
            node.prev = "editable"

        # It will only run generation and imports once
        node = install_node.nodes[0]
        conanfile = node.conanfile
        output = conanfile.output
        output.info("Rewriting files of editable package "
                    "'{}' at '{}'".format(conanfile.name, conanfile.generators_folder))
        write_generators(conanfile)
        copied_files = run_imports(conanfile)
        report_copied_files(copied_files, output)

    def _handle_node_build(self, package, pkg_layout):
        node = package.nodes[0]
        pref = node.pref
        assert pref.package_id, "Package-ID without value"
        assert pref.package_id != PACKAGE_ID_UNKNOWN, "Package-ID error: %s" % str(pref)
        assert pkg_layout, "The pkg_layout should be declared here"
        assert node.binary == BINARY_BUILD

        with pkg_layout.package_lock():
            assert node.prev is None, "PREV for %s to be built should be None" % str(pref)
            pkg_layout.package_remove()
            with pkg_layout.set_dirty_context_manager():
                pref = self._build_package(node, pkg_layout)
            assert node.prev, "Node PREV shouldn't be empty"
            assert node.pref.revision, "Node PREF revision shouldn't be empty"
            assert pref.revision is not None, "PREV for %s to be built is None" % str(pref)
            # at this point the package reference should be complete
            pkg_layout.reference = ConanReference(pref)
            self._cache.assign_prev(pkg_layout)
            # Make sure the current conanfile.folders is updated (it is later in package_info(),
            # but better make sure here, and be able to report the actual folder in case
            # something fails)
            node.conanfile.folders.set_base_package(pkg_layout.package())
            self._out.info("Package folder %s" % node.conanfile.package_folder)

    def _build_package(self, node, pkg_layout):
        builder = _PackageBuilder(self._app, node.conanfile.output)
        pref = builder.build_package(node, pkg_layout)
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
