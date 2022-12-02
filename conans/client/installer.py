import os
import shutil
import time
from multiprocessing.pool import ThreadPool

from conan.api.output import ConanOutput
from conans.client.conanfile.build import run_build_method
from conans.client.conanfile.package import run_package_method
from conans.client.generators import write_generators
from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_EDITABLE, \
    BINARY_UPDATE, BINARY_EDITABLE_BUILD
from conans.client.graph.install_graph import InstallGraph
from conans.client.source import retrieve_exports_sources, config_source
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.build_info import CppInfo
from conans.model.package_ref import PkgReference
from conans.paths import CONANINFO
from conans.util.files import clean_dirty, is_dirty, mkdir, rmdir, save, set_dirty, chdir
from conans.util.tracer import log_package_built, log_package_got_from_local_cache


def build_id(conan_file):
    if hasattr(conan_file, "build_id"):
        # construct new ConanInfo
        build_id_info = conan_file.info.clone()
        conan_file.info_build = build_id_info
        # effectively call the user function to change the package values
        with conanfile_exception_formatter(conan_file, "build_id"):
            conan_file.build_id()
        # compute modified ID
        return build_id_info.package_id()
    return None


class _PackageBuilder(object):

    def __init__(self, app):
        self._app = app
        self._cache = app.cache
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
            recipe_ref = pref.ref
            build_prev = self._cache.get_matching_build_id(recipe_ref, recipe_build_id)
            build_prev = build_prev or pref

            # We are trying to build a package id different from the one that has the
            # build_folder but belongs to the same recipe revision, so reuse the build_folder
            # from the one that is already build
            if build_prev.package_id != pref.package_id:
                other_pkg_layout = self._cache.pkg_layout(build_prev)
                build_folder = other_pkg_layout.build()
                skip_build = True

        if is_dirty(build_folder):
            conanfile.output.warning("Build folder is dirty, removing it: %s" % build_folder)
            rmdir(build_folder)
            clean_dirty(build_folder)

        if skip_build and os.path.exists(build_folder):
            conanfile.output.info("Won't be built, using previous build folder as defined "
                                  "in build_id()")

        return build_folder, skip_build

    def _prepare_sources(self, conanfile, pref, recipe_layout, enabled_remotes):
        export_source_folder = recipe_layout.export_sources()
        source_folder = recipe_layout.source()

        retrieve_exports_sources(self._remote_manager, recipe_layout, conanfile, pref.ref,
                                 enabled_remotes)

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_export_sources(source_folder)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_package(None)

        config_source(export_source_folder, conanfile, self._hook_manager)

    @staticmethod
    def _copy_sources(conanfile, source_folder, build_folder):
        # Copies the sources to the build-folder, unless no_copy_source is defined
        rmdir(build_folder)
        if not getattr(conanfile, 'no_copy_source', False):
            conanfile.output.info('Copying sources to build folder')
            try:
                shutil.copytree(source_folder, build_folder, symlinks=True)
            except Exception as e:
                msg = str(e)
                if "206" in msg:  # System error shutil.Error 206: Filename or extension too long
                    msg += "\nUse short_paths=True if paths too long"
                raise ConanException("%s\nError copying sources to build folder" % msg)

    def _build(self, conanfile, pref):
        write_generators(conanfile, self._hook_manager)

        try:
            run_build_method(conanfile, self._hook_manager)
            conanfile.output.success("Package '%s' built" % pref.package_id)
            conanfile.output.info("Build folder %s" % conanfile.build_folder)
        except Exception as exc:
            conanfile.output.error("\nPackage '%s' build failed" % pref.package_id)
            conanfile.output.warning("Build folder %s" % conanfile.build_folder)
            if isinstance(exc, ConanExceptionInUserConanfileMethod):
                raise exc
            raise ConanException(exc)

    def _package(self, conanfile, pref):
        # Creating ***info.txt files
        save(os.path.join(conanfile.folders.base_build, CONANINFO), conanfile.info.dumps())
        conanfile.output.info("Generated %s" % CONANINFO)

        package_id = pref.package_id
        # Do the actual copy, call the conanfile.package() method
        # While installing, the infos goes to build folder
        prev = run_package_method(conanfile, package_id, self._hook_manager, pref.ref)

        # FIXME: Conan 2.0 Clear the registry entry (package ref)
        return prev

    def build_package(self, node, package_layout, remotes):
        t1 = time.time()

        conanfile = node.conanfile
        pref = node.pref

        # TODO: cache2.0 fix this
        recipe_layout = self._cache.ref_layout(pref.ref)

        base_source = recipe_layout.source()
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
        with chdir(base_build):
            conanfile.output.info('Building your package in %s' % base_build)
            try:
                src = base_source if getattr(conanfile, 'no_copy_source', False) else base_build
                conanfile.folders.set_base_source(src)
                conanfile.folders.set_base_build(base_build)
                conanfile.folders.set_base_package(base_package)
                # In local cache, generators folder always in build_folder
                conanfile.folders.set_base_generators(base_build)

                if not skip_build:
                    # In local cache, install folder always is build_folder
                    self._build(conanfile, pref)
                    clean_dirty(base_build)

                prev = self._package(conanfile, pref)
                assert prev
                node.prev = prev
                log_package_built(pref, time.time() - t1)
            except ConanException as exc:
                raise exc

        return node.pref


def call_system_requirements(conanfile):
    if hasattr(conanfile, "system_requirements"):
        with conanfile_exception_formatter(conanfile, "system_requirements"):
            conanfile.system_requirements()


class BinaryInstaller:
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """
    def __init__(self, app):
        self._app = app
        self._cache = app.cache
        self._remote_manager = app.remote_manager
        self._hook_manager = app.hook_manager

    def install(self, deps_graph, remotes):
        assert not deps_graph.error, "This graph cannot be installed: {}".format(deps_graph)

        ConanOutput().title("Installing (downloading, building) binaries...")

        # order by levels and separate the root node (ref=None) from the rest
        install_graph = InstallGraph(deps_graph)
        install_graph.raise_errors()
        install_order = install_graph.install_order()

        self._download_bulk(install_order)
        for level in install_order:
            for install_reference in level:
                for package in install_reference.packages.values():
                    self._handle_package(package, install_reference, remotes)

    def _download_bulk(self, install_order):
        """ executes the download of packages (both download and update), only once for a given
        PREF
        """
        downloads = []
        for level in install_order:
            for node in level:
                for package in node.packages.values():
                    if package.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                        downloads.append(package)
        if not downloads:
            return

        parallel = self._cache.new_config.get("core.download:parallel", check_type=int)
        if parallel is not None:
            ConanOutput().info("Downloading binary packages in %s parallel threads" % parallel)
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
        assert node.pref.timestamp is not None
        self._remote_manager.get_package(node.conanfile, node.pref, node.binary_remote)

    def _handle_package(self, package, install_reference, remotes):
        if package.binary in (BINARY_EDITABLE, BINARY_EDITABLE_BUILD):
            self._handle_node_editable(package)
            return

        assert package.binary in (BINARY_CACHE, BINARY_BUILD, BINARY_DOWNLOAD, BINARY_UPDATE)
        assert install_reference.ref.revision is not None, "Installer should receive RREV always"

        pref = PkgReference(install_reference.ref, package.package_id, package.prev)
        if pref.revision is None:
            assert package.binary == BINARY_BUILD
            package_layout = self._cache.create_build_pkg_layout(pref)
        else:
            package_layout = self._cache.get_or_create_pkg_layout(pref)

        call_system_requirements(package.nodes[0].conanfile)

        if package.binary == BINARY_BUILD:
            self._handle_node_build(package, package_layout, remotes)
            # Just in case it was recomputed
            package.package_id = package.nodes[0].pref.package_id  # Just in case it was recomputed
            package.prev = package.nodes[0].pref.revision
            package.binary = package.nodes[0].binary
            pref = PkgReference(install_reference.ref, package.package_id, package.prev)
        elif package.binary == BINARY_CACHE:
            node = package.nodes[0]
            pref = node.pref
            assert node.prev, "PREV for %s is None" % str(pref)
            node.conanfile.output.success('Already installed!')
            log_package_got_from_local_cache(pref)

        # Make sure that all nodes with same pref compute package_info()
        pkg_folder = package_layout.package()
        assert os.path.isdir(pkg_folder), "Pkg '%s' folder must exist: %s" % (str(pref), pkg_folder)
        for n in package.nodes:
            n.prev = pref.revision  # Make sure the prev is assigned
            conanfile = n.conanfile
            # Call the info method
            conanfile.folders.set_base_package(pkg_folder)
            conanfile.folders.set_base_source(None)
            conanfile.folders.set_base_build(None)
            self._call_package_info(conanfile, pkg_folder, is_editable=False)

    def _handle_node_editable(self, install_node):
        # It will only run generation
        node = install_node.nodes[0]
        conanfile = node.conanfile
        ref = node.ref
        editable = self._cache.editable_packages.get(ref)
        conanfile_path = editable["path"]
        output_folder = editable.get("output_folder")

        # TODO: Check, this assumes the folder is always the conanfile one
        base_path = os.path.dirname(conanfile_path)
        conanfile.folders.set_base_folders(base_path, output_folder)
        output = conanfile.output
        output.info("Rewriting files of editable package "
                    "'{}' at '{}'".format(conanfile.name, conanfile.generators_folder))
        write_generators(conanfile, self._hook_manager)
        call_system_requirements(conanfile)

        if node.binary == BINARY_EDITABLE_BUILD:
            run_build_method(conanfile, self._hook_manager)

        for node in install_node.nodes:
            # Get source of information
            conanfile = node.conanfile
            # New editables mechanism based on Folders
            conanfile.folders.set_base_package(output_folder or base_path)
            conanfile.folders.set_base_source(base_path)
            conanfile.folders.set_base_build(output_folder or base_path)
            conanfile.folders.set_base_generators(output_folder or base_path)
            # Need a temporary package revision for package_revision_mode
            # Cannot be PREV_UNKNOWN otherwise the consumers can't compute their packageID
            node.prev = "editable"
            # TODO: Check this base_path usage for editable when not defined
            self._call_package_info(conanfile, package_folder=base_path, is_editable=True)

    def _handle_node_build(self, package, pkg_layout, remotes):
        node = package.nodes[0]
        pref = node.pref
        assert pref.package_id, "Package-ID without value"
        assert pkg_layout, "The pkg_layout should be declared here"
        assert node.binary == BINARY_BUILD
        assert node.prev is None, "PREV for %s to be built should be None" % str(pref)

        with pkg_layout.package_lock():
            pkg_layout.package_remove()
            with pkg_layout.set_dirty_context_manager():
                builder = _PackageBuilder(self._app)
                pref = builder.build_package(node, pkg_layout, remotes)
            assert node.prev, "Node PREV shouldn't be empty"
            assert node.pref.revision, "Node PREF revision shouldn't be empty"
            assert pref.revision is not None, "PREV for %s to be built is None" % str(pref)
            # at this point the package reference should be complete
            pkg_layout.reference = pref
            self._cache.assign_prev(pkg_layout)
            # Make sure the current conanfile.folders is updated (it is later in package_info(),
            # but better make sure here, and be able to report the actual folder in case
            # something fails)
            node.conanfile.folders.set_base_package(pkg_layout.package())
            node.conanfile.output.info("Package folder %s" % node.conanfile.package_folder)

    def _call_package_info(self, conanfile, package_folder, is_editable):

        with chdir(package_folder):
            with conanfile_exception_formatter(conanfile, "package_info"):
                self._hook_manager.execute("pre_package_info", conanfile=conanfile)

                if hasattr(conanfile, "package_info"):
                    conanfile.package_info()

                # TODO: Check this package_folder usage for editable when not defined
                conanfile.cpp.package.set_relative_base_folder(package_folder)

                if is_editable:
                    # Adjust the folders of the layout to consolidate the rootfolder of the
                    # cppinfos inside

                    # convert directory entries to be relative to the declared folders.build
                    build_cppinfo = conanfile.cpp.build.copy()
                    build_cppinfo.set_relative_base_folder(conanfile.build_folder)
                    conanfile.layouts.build.set_relative_base_folder(conanfile.build_folder)

                    # convert directory entries to be relative to the declared folders.source
                    source_cppinfo = conanfile.cpp.source.copy()
                    source_cppinfo.set_relative_base_folder(conanfile.source_folder)
                    conanfile.layouts.source.set_relative_base_folder(conanfile.source_folder)

                    full_editable_cppinfo = CppInfo()
                    full_editable_cppinfo.merge(source_cppinfo)
                    full_editable_cppinfo.merge(build_cppinfo)
                    # In editables if we defined anything in the cpp infos we want to discard
                    # the one defined in the conanfile cpp_info
                    conanfile.cpp_info.merge(full_editable_cppinfo, overwrite=True)

                    # Paste the editable cpp_info but prioritizing it, only if a
                    # variable is not declared at build/source, the package will keep the value
                    conanfile.buildenv_info.compose_env(conanfile.layouts.source.buildenv_info)
                    conanfile.buildenv_info.compose_env(conanfile.layouts.build.buildenv_info)
                    conanfile.runenv_info.compose_env(conanfile.layouts.source.runenv_info)
                    conanfile.runenv_info.compose_env(conanfile.layouts.build.runenv_info)
                    conanfile.conf_info.compose_conf(conanfile.layouts.source.conf_info)
                    conanfile.conf_info.compose_conf(conanfile.layouts.build.conf_info)
                else:
                    conanfile.layouts.package.set_relative_base_folder(conanfile.package_folder)
                    conanfile.buildenv_info.compose_env(conanfile.layouts.package.buildenv_info)
                    conanfile.runenv_info.compose_env(conanfile.layouts.package.runenv_info)
                    conanfile.conf_info.compose_conf(conanfile.layouts.package.conf_info)

                self._hook_manager.execute("post_package_info", conanfile=conanfile)

        conanfile.cpp_info.check_component_requires(conanfile)
