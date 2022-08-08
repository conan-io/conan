import os
import shutil
import textwrap
import time
from multiprocessing.pool import ThreadPool

from conans.client import tools
from conans.client.conanfile.build import run_build_method
from conans.client.conanfile.package import run_package_method
from conans.client.file_copier import report_copied_files
from conans.client.generators import TXTGenerator, write_toolchain
from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_EDITABLE, \
    BINARY_MISSING, BINARY_SKIP, BINARY_UPDATE, BINARY_UNKNOWN, CONTEXT_HOST, BINARY_INVALID
from conans.client.importer import remove_imports, run_imports
from conans.client.packager import update_package_metadata
from conans.client.recorder.action_recorder import INSTALL_ERROR_BUILDING, INSTALL_ERROR_MISSING, \
    INSTALL_ERROR_MISSING_BUILD_FOLDER
from conans.client.source import retrieve_exports_sources, config_source
from conans.client.tools.env import pythonpath
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter, ConanInvalidConfiguration)
from conans.model.build_info import CppInfo, DepCppInfo, CppInfoDefaultValues
from conans.model.conan_file import ConanFile
from conans.model.editable_layout import EditableLayout
from conans.model.env_info import EnvInfo
from conans.model.graph_info import GraphInfo
from conans.model.graph_lock import GraphLockFile
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.new_build_info import NewCppInfo, fill_old_cppinfo
from conans.model.ref import PackageReference
from conans.model.user_info import DepsUserInfo
from conans.model.user_info import UserInfo
from conans.paths import BUILD_INFO, CONANINFO, RUN_LOG_NAME
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


def add_env_conaninfo(conan_file, subtree_libnames):
    for package_name, env_vars in conan_file._conan_env_values.data.items():
        for name, value in env_vars.items():
            if not package_name or package_name in subtree_libnames or \
                    package_name == conan_file.name:
                conan_file.info.env_values.add(name, value, package_name)


class _PackageBuilder(object):
    def __init__(self, cache, output, hook_manager, remote_manager, generators):
        self._cache = cache
        self._output = output
        self._hook_manager = hook_manager
        self._remote_manager = remote_manager
        self._generator_manager = generators

    def _get_build_folder(self, conanfile, package_layout, pref, keep_build, recorder):
        # Build folder can use a different package_ID if build_id() is defined.
        # This function decides if the build folder should be re-used (not build again)
        # and returns the build folder
        new_id = build_id(conanfile)
        build_pref = PackageReference(pref.ref, new_id) if new_id else pref
        build_folder = package_layout.build(build_pref)

        if is_dirty(build_folder):
            self._output.warn("Build folder is dirty, removing it: %s" % build_folder)
            rmdir(build_folder)
            clean_dirty(build_folder)

        # Decide if the build folder should be kept
        skip_build = conanfile.develop and keep_build
        if skip_build:
            self._output.info("Won't be built as specified by --keep-build")
            if not os.path.exists(build_folder):
                msg = "--keep-build specified, but build folder not found"
                recorder.package_install_error(pref, INSTALL_ERROR_MISSING_BUILD_FOLDER,
                                               msg, remote_name=None)
                raise ConanException(msg)
        elif build_pref != pref and os.path.exists(build_folder) and hasattr(conanfile, "build_id"):
            self._output.info("Won't be built, using previous build folder as defined in build_id()")
            skip_build = True

        return build_folder, skip_build

    def _prepare_sources(self, conanfile, pref, package_layout, remotes):
        export_folder = package_layout.export()
        export_source_folder = package_layout.export_sources()
        scm_sources_folder = package_layout.scm_sources()
        conanfile_path = package_layout.conanfile()
        source_folder = package_layout.source()

        retrieve_exports_sources(self._remote_manager, self._cache, conanfile, pref.ref, remotes)

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_export_sources(source_folder)
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
                run_build_method(conanfile, self._hook_manager, reference=pref.ref, package_id=pref.id)
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

    def _package(self, conanfile, pref, package_layout, conanfile_path):
        # FIXME: Is weak to assign here the recipe_hash
        manifest = package_layout.recipe_manifest()
        conanfile.info.recipe_hash = manifest.summary_hash

        # Creating ***info.txt files
        save(os.path.join(conanfile.folders.base_build, CONANINFO), conanfile.info.dumps())
        self._output.info("Generated %s" % CONANINFO)
        save(os.path.join(conanfile.folders.base_build, BUILD_INFO),
             TXTGenerator(conanfile).content)
        self._output.info("Generated %s" % BUILD_INFO)

        package_id = pref.id
        # Do the actual copy, call the conanfile.package() method
        # While installing, the infos goes to build folder
        conanfile.folders.set_base_install(conanfile.folders.base_build)

        prev = run_package_method(conanfile, package_id, self._hook_manager, conanfile_path,
                                  pref.ref)

        update_package_metadata(prev, package_layout, package_id, pref.ref.revision)

        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(conanfile.folders.base_package)
        # FIXME: Conan 2.0 Clear the registry entry (package ref)
        return prev

    def build_package(self, node, keep_build, recorder, remotes):
        t1 = time.time()

        conanfile = node.conanfile
        pref = node.pref

        package_layout = self._cache.package_layout(pref.ref, conanfile.short_paths)
        base_source = package_layout.source()
        conanfile_path = package_layout.conanfile()
        base_package = package_layout.package(pref)

        base_build, skip_build = self._get_build_folder(conanfile, package_layout,
                                                               pref, keep_build, recorder)
        # PREPARE SOURCES
        if not skip_build:
            with package_layout.conanfile_write_lock(self._output):
                set_dirty(base_build)
                self._prepare_sources(conanfile, pref, package_layout, remotes)
                self._copy_sources(conanfile, base_source, base_build)

        # BUILD & PACKAGE
        with package_layout.conanfile_read_lock(self._output):
            self._output.info('Building your package in %s' % base_build)
            try:
                if getattr(conanfile, 'no_copy_source', False):
                    conanfile.folders.set_base_source(base_source)
                else:
                    conanfile.folders.set_base_source(base_build)

                conanfile.folders.set_base_build(base_build)
                conanfile.folders.set_base_imports(base_build)
                conanfile.folders.set_base_package(base_package)
                # In local cache, generators folder always in build_folder
                conanfile.folders.set_base_generators(base_build)

                if not skip_build:
                    # In local cache, install folder always is build_folder
                    conanfile.folders.set_base_install(base_build)
                    self._build(conanfile, pref)
                    clean_dirty(base_build)

                prev = self._package(conanfile, pref, package_layout, conanfile_path)
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


def _handle_system_requirements(conan_file, pref, cache, out):
    """ check first the system_reqs/system_requirements.txt existence, if not existing
    check package/sha1/

    Used after remote package retrieving and before package building
    """
    # TODO: Check if this idiom should be generalize to all methods defined in base ConanFile
    # Instead of calling empty methods
    if type(conan_file).system_requirements == ConanFile.system_requirements:
        return

    package_layout = cache.package_layout(pref.ref)
    system_reqs_path = package_layout.system_reqs()
    system_reqs_package_path = package_layout.system_reqs_package(pref)
    if os.path.exists(system_reqs_path) or os.path.exists(system_reqs_package_path):
        return

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
                graph_lock, keep_build=False):
        # order by levels and separate the root node (ref=None) from the rest
        nodes_by_level = deps_graph.by_levels()
        root_level = nodes_by_level.pop()
        root_node = root_level[0]
        # Get the nodes in order and if we have to build them
        self._out.info("Installing (downloading, building) binaries...")
        self._build(nodes_by_level, keep_build, root_node, profile_host, profile_build,
                    graph_lock, remotes, build_mode, update)

    @staticmethod
    def _classify(nodes_by_level):
        missing, invalid, downloads = [], [], []
        for level in nodes_by_level:
            for node in level:
                if node.binary == BINARY_MISSING:
                    missing.append(node)
                elif node.binary == BINARY_INVALID:
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
            Use 'conan search %s --table=table.html -r=remote' and open the table.html file to see available packages
            Or try to build locally from sources with '%s'

            More Info at 'https://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package'
            ''' % (missing_pkgs, ref, build_str)))

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
            layout = self._cache.package_layout(n.pref.ref, n.conanfile.short_paths)
            # We cannot embed the package_lock inside the remote.get_package()
            # because the handle_node_cache has its own lock
            with layout.package_lock(n.pref):
                self._download_pkg(layout, n)

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

    def _download_pkg(self, layout, node):
        self._remote_manager.get_package(node.conanfile, node.pref, layout, node.binary_remote,
                                         node.conanfile.output, self._recorder)

    def _build(self, nodes_by_level, keep_build, root_node, profile_host, profile_build, graph_lock,
               remotes, build_mode, update):
        using_build_profile = bool(profile_build)
        missing, invalid, downloads = self._classify(nodes_by_level)
        if invalid:
            msg = ["There are invalid packages (packages that cannot exist for this configuration):"]
            for node in invalid:
                if node.cant_build:
                    msg.append("{}: Cannot build "
                               "for this configuration: {}".format(node.conanfile,
                                                                   node.cant_build))
                else:
                    msg.append("{}: Invalid ID: {}".format(node.conanfile,
                                                           node.conanfile.info.invalid))
            raise ConanInvalidConfiguration("\n".join(msg))
        self._raise_missing(missing)
        processed_package_refs = {}
        self._download(downloads, processed_package_refs)

        for level in nodes_by_level:
            for node in level:
                ref, conan_file = node.ref, node.conanfile
                output = conan_file.output

                self._propagate_info(node, using_build_profile)
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
                    if node.binary == BINARY_EDITABLE:
                        self._handle_node_editable(node, profile_host, profile_build, graph_lock)
                        # Need a temporary package revision for package_revision_mode
                        # Cannot be PREV_UNKNOWN otherwise the consumers can't compute their packageID
                        node.prev = "editable"
                    else:
                        _handle_system_requirements(conan_file, node.pref, self._cache, output)
                        self._handle_node_cache(node, keep_build, processed_package_refs, remotes)

        # Finally, propagate information to root node (ref=None)
        self._propagate_info(root_node, using_build_profile)

    def _handle_node_editable(self, node, profile_host, profile_build, graph_lock):
        # Get source of information
        conanfile = node.conanfile
        ref = node.ref
        package_layout = self._cache.package_layout(ref)
        base_path = package_layout.base_folder()

        if hasattr(conanfile, "layout"):
            conanfile.folders.set_base_folders(base_path, package_layout.output_folder)
        else:
            conanfile.folders.set_base_package(base_path)
            conanfile.folders.set_base_source(None)
            conanfile.folders.set_base_build(None)
            conanfile.folders.set_base_install(None)

        self._call_package_info(conanfile, package_folder=base_path, ref=ref, is_editable=True)

        # New editables mechanism based on Folders
        if hasattr(conanfile, "layout"):
            output = conanfile.output
            output.info("Rewriting files of editable package "
                        "'{}' at '{}'".format(conanfile.name, conanfile.generators_folder))
            self._generator_manager.write_generators(conanfile, conanfile.install_folder,
                                                     conanfile.generators_folder, output)
            write_toolchain(conanfile, conanfile.generators_folder, output)
            output.info("Generated toolchain")
            graph_info_node = GraphInfo(profile_host, root_ref=node.ref)
            graph_info_node.options = node.conanfile.options.values
            graph_info_node.graph_lock = graph_lock
            graph_info_node.save(base_path)
            output.info("Generated conan.lock")
            copied_files = run_imports(conanfile)
            report_copied_files(copied_files, output)
            return

        node.conanfile.cpp_info.filter_empty = False
        # OLD EDITABLE LAYOUTS:
        # Try with package-provided file
        editable_cpp_info = package_layout.editable_cpp_info()
        if editable_cpp_info:
            editable_cpp_info.apply_to(ref,
                                       conanfile.cpp_info,
                                       settings=conanfile.settings,
                                       options=conanfile.options)
            build_folder = editable_cpp_info.folder(ref, EditableLayout.BUILD_FOLDER,
                                                    settings=conanfile.settings,
                                                    options=conanfile.options)
            if build_folder is not None:
                build_folder = os.path.join(base_path, build_folder)
                output = conanfile.output
                self._generator_manager.write_generators(conanfile, build_folder, build_folder, output)
                write_toolchain(conanfile, build_folder, output)
                save(os.path.join(build_folder, CONANINFO), conanfile.info.dumps())
                output.info("Generated %s" % CONANINFO)

                graph_info_node = GraphInfo(profile_host, root_ref=node.ref)
                graph_info_node.options = node.conanfile.options.values
                graph_info_node.graph_lock = graph_lock
                graph_info_node.save(build_folder)
                output.info("Generated graphinfo")
                graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
                graph_lock_file.save(os.path.join(build_folder, "conan.lock"))

                save(os.path.join(build_folder, BUILD_INFO), TXTGenerator(conanfile).content)
                output.info("Generated %s" % BUILD_INFO)
                # Build step might need DLLs, binaries as protoc to generate source files
                # So execute imports() before build, storing the list of copied_files
                conanfile.folders.set_base_imports(build_folder)
                copied_files = run_imports(conanfile)
                report_copied_files(copied_files, output)

    def _handle_node_cache(self, node, keep_build, processed_package_references, remotes):
        pref = node.pref
        assert pref.id, "Package-ID without value"
        assert pref.id != PACKAGE_ID_UNKNOWN, "Package-ID error: %s" % str(pref)
        conanfile = node.conanfile
        output = conanfile.output

        layout = self._cache.package_layout(pref.ref, conanfile.short_paths)

        with layout.package_lock(pref):
            bare_pref = PackageReference(pref.ref, pref.id)
            processed_prev = processed_package_references.get(bare_pref)
            if processed_prev is None:  # This package-id has not been processed before
                if node.binary == BINARY_BUILD:
                    assert node.prev is None, "PREV for %s to be built should be None" % str(pref)
                    layout.package_remove(pref)
                    with layout.set_dirty_context_manager(pref):
                        pref = self._build_package(node, output, keep_build, remotes)
                    assert node.prev, "Node PREV shouldn't be empty"
                    assert node.pref.revision, "Node PREF revision shouldn't be empty"
                    assert pref.revision is not None, "PREV for %s to be built is None" % str(pref)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    # this can happen after a re-evaluation of packageID with Package_ID_unknown
                    self._download_pkg(layout, node)
                elif node.binary == BINARY_CACHE:
                    assert node.prev, "PREV for %s is None" % str(pref)
                    output.success('Already installed!')
                    log_package_got_from_local_cache(pref)
                    self._recorder.package_fetched_from_cache(pref)
                processed_package_references[bare_pref] = node.prev
            else:
                # We need to update the PREV of this node, as its processing has been skipped,
                # but it could be that another node with same PREF was built and obtained a new PREV
                node.prev = processed_prev

            package_folder = layout.package(pref)
            assert os.path.isdir(package_folder), ("Package '%s' folder must exist: %s\n"
                                                   % (str(pref), package_folder))
            # Call the info method
            conanfile.folders.set_base_package(package_folder)
            conanfile.folders.set_base_source(None)
            conanfile.folders.set_base_build(None)
            conanfile.folders.set_base_install(None)
            self._call_package_info(conanfile, package_folder, ref=pref.ref, is_editable=False)
            self._recorder.package_cpp_info(pref, conanfile.cpp_info)

    def _build_package(self, node, output, keep_build, remotes):
        conanfile = node.conanfile
        # It is necessary to complete the sources of python requires, which might be used
        # Only the legacy python_requires allow this
        python_requires = getattr(conanfile, "python_requires", None)
        if python_requires and isinstance(python_requires, dict):  # Old legacy python_requires
            for python_require in python_requires.values():
                assert python_require.ref.revision is not None, \
                    "Installer should receive python_require.ref always"
                retrieve_exports_sources(self._remote_manager, self._cache,
                                         python_require.conanfile, python_require.ref, remotes)

        builder = _PackageBuilder(self._cache, output, self._hook_manager, self._remote_manager,
                                  self._generator_manager)
        pref = builder.build_package(node, keep_build, self._recorder, remotes)
        if node.graph_lock_node:
            node.graph_lock_node.prev = pref.revision
        return pref

    def _propagate_info(self, node, using_build_profile):
        # it is necessary to recompute
        # the node transitive information necessary to compute the package_id
        # as it will be used by reevaluate_node() when package_revision_mode is used and
        # PACKAGE_ID_UNKNOWN happens due to unknown revisions
        self._binaries_analyzer.package_id_transitive_reqs(node)
        # Get deps_cpp_info from upstream nodes
        node_order = [n for n in node.public_closure if n.binary != BINARY_SKIP]
        # List sort is stable, will keep the original order of the closure, but prioritize levels
        conan_file = node.conanfile
        # FIXME: Not the best place to assign the _conan_using_build_profile
        conan_file._conan_using_build_profile = using_build_profile
        transitive = [it for it in node.transitive_closure.values()]

        br_host = []
        for it in node.dependencies:
            if it.require.build_require_context == CONTEXT_HOST:
                br_host.extend(it.dst.transitive_closure.values())

        # Initialize some members if we are using different contexts
        if using_build_profile:
            conan_file.user_info_build = DepsUserInfo()

        for n in node_order:
            if n not in transitive:
                conan_file.output.info("Applying build-requirement: %s" % str(n.ref))

            dep_cpp_info = n.conanfile._conan_dep_cpp_info

            if not using_build_profile:  # Do not touch anything
                conan_file.deps_user_info[n.ref.name] = n.conanfile.user_info
                conan_file.deps_cpp_info.add(n.ref.name, dep_cpp_info)
                conan_file.deps_env_info.update(n.conanfile.env_info, n.ref.name)
            else:
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

        # Update the info but filtering the package values that not apply to the subtree
        # of this current node and its dependencies.
        subtree_libnames = [node.ref.name for node in node_order]
        add_env_conaninfo(conan_file, subtree_libnames)

    def _call_package_info(self, conanfile, package_folder, ref, is_editable):
        conanfile.cpp_info = CppInfo(conanfile.name, package_folder)
        conanfile.cpp_info.version = conanfile.version
        conanfile.cpp_info.description = conanfile.description

        conanfile.env_info = EnvInfo()
        conanfile.user_info = UserInfo()

        # Get deps_cpp_info from upstream nodes
        public_deps = [name for name, req in conanfile.requires.items() if not req.private
                       and not req.override]
        conanfile.cpp_info.public_deps = public_deps
        # Once the node is build, execute package info, so it has access to the
        # package folder and artifacts
        # Minimal pythonpath, not the whole context, make it 50% slower
        # FIXME Conan 2.0, Remove old ways of reusing python code
        with pythonpath(conanfile):
            with tools.chdir(package_folder):
                with conanfile_exception_formatter(str(conanfile), "package_info"):
                    self._hook_manager.execute("pre_package_info", conanfile=conanfile,
                                               reference=ref)
                    if hasattr(conanfile, "layout"):
                        # Old cpp info without defaults (the defaults are in the new one)
                        conanfile.cpp_info = CppInfo(conanfile.name, package_folder,
                                                     default_values=CppInfoDefaultValues())
                        # Note: Remember that this is not needed for Conan 2.x
                        # Let's avoid losing this information.
                        conanfile.cpp_info.version = conanfile.version
                        conanfile.cpp_info.description = conanfile.description
                        conanfile.cpp_info.public_deps = public_deps

                        if not is_editable:
                            # Copy the infos.package into the old cppinfo
                            fill_old_cppinfo(conanfile.cpp.package, conanfile.cpp_info)
                        else:
                            conanfile.cpp_info.filter_empty = False

                    conanfile.package_info()

                    if hasattr(conanfile, "layout") and is_editable:
                        # Adjust the folders of the layout to consolidate the rootfolder of the
                        # cppinfos inside
                        # convert directory entries to be relative to the declared folders.build
                        conanfile.cpp.build.set_relative_base_folder(conanfile.build_folder)

                        # convert directory entries to be relative to the declared folders.source
                        conanfile.cpp.source.set_relative_base_folder(conanfile.source_folder)

                        full_editable_cppinfo = NewCppInfo()
                        full_editable_cppinfo.merge(conanfile.cpp.source)
                        full_editable_cppinfo.merge(conanfile.cpp.build)
                        # Paste the editable cpp_info but prioritizing it, only if a
                        # variable is not declared at build/source, the package will keep the value
                        fill_old_cppinfo(full_editable_cppinfo, conanfile.cpp_info)

                    if conanfile._conan_dep_cpp_info is None:
                        try:
                            if not is_editable and not hasattr(conanfile, "layout"):
                                # FIXME: The default for the cppinfo from build are not the same
                                #        so this check fails when editable
                                # FIXME: Remove when new cppinfo model. If using the layout method
                                #        the cppinfo object is filled from self.cpp.package new
                                #        model and we cannot check if the defaults have been modified
                                #        because it doesn't exist in the new model where the defaults
                                #        for the components are always empty
                                conanfile.cpp_info._raise_incorrect_components_definition(
                                    conanfile.name, conanfile.requires)
                        except ConanException as e:
                            raise ConanException("%s package_info(): %s" % (str(conanfile), e))
                        conanfile._conan_dep_cpp_info = DepCppInfo(conanfile.cpp_info)
                    self._hook_manager.execute("post_package_info", conanfile=conanfile,
                                               reference=ref)
