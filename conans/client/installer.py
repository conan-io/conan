import os
import shutil
import time

from conans.client import tools
from conans.client.file_copier import report_copied_files
from conans.client.generators import TXTGenerator, write_generators
from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING, \
    BINARY_SKIP, BINARY_UPDATE, BINARY_EDITABLE
from conans.client.importer import remove_imports, run_imports
from conans.client.packager import create_package
from conans.client.recorder.action_recorder import INSTALL_ERROR_BUILDING, INSTALL_ERROR_MISSING, \
    INSTALL_ERROR_MISSING_BUILD_FOLDER
from conans.client.source import complete_recipe_sources, config_source
from conans.client.tools.env import pythonpath
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.build_info import CppInfo
from conans.model.conan_file import get_env_context_manager
from conans.model.editable_layout import EditableLayout
from conans.model.env_info import EnvInfo
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.model.user_info import UserInfo
from conans.paths import BUILD_INFO, CONANINFO, RUN_LOG_NAME
from conans.util.env_reader import get_env
from conans.util.files import (clean_dirty, is_dirty, make_read_only, mkdir, rmdir, save, set_dirty)
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
    def __init__(self, cache, output, hook_manager, remote_manager):
        self._cache = cache
        self._output = output
        self._hook_manager = hook_manager
        self._remote_manager = remote_manager

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

    def _prepare_sources(self, conanfile, pref, package_layout, conanfile_path, source_folder,
                         build_folder, package_folder):
        export_folder = package_layout.export()
        export_source_folder = package_layout.export_sources()

        complete_recipe_sources(self._remote_manager, self._cache, conanfile, pref.ref)
        try:
            rmdir(build_folder)
            rmdir(package_folder)
        except OSError as e:
            raise ConanException("%s\n\nCouldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % str(e))

        config_source(export_folder, export_source_folder, source_folder,
                      conanfile, self._output, conanfile_path, pref.ref,
                      self._hook_manager, self._cache)

        if not getattr(conanfile, 'no_copy_source', False):
            self._output.info('Copying sources to build folder')
            try:
                shutil.copytree(source_folder, build_folder, symlinks=True)
            except Exception as e:
                msg = str(e)
                if "206" in msg:  # System error shutil.Error 206: Filename or extension too long
                    msg += "\nUse short_paths=True if paths too long"
                raise ConanException("%s\nError copying sources to build folder" % msg)
            logger.debug("BUILD: Copied to %s", build_folder)
            logger.debug("BUILD: Files copied %s", ",".join(os.listdir(build_folder)))

    def _build(self, conanfile, pref, build_folder):
        # Read generators from conanfile and generate the needed files
        logger.info("GENERATORS: Writing generators")
        write_generators(conanfile, build_folder, self._output)

        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files
        copied_files = run_imports(conanfile, build_folder)

        try:
            self._hook_manager.execute("pre_build", conanfile=conanfile,
                                       reference=pref.ref, package_id=pref.id)
            logger.debug("Call conanfile.build() with files in build folder: %s",
                         os.listdir(build_folder))
            self._output.highlight("Calling build()")
            with conanfile_exception_formatter(str(conanfile), "build"):
                conanfile.build()

            self._output.success("Package '%s' built" % pref.id)
            self._output.info("Build folder %s" % build_folder)
            self._hook_manager.execute("post_build", conanfile=conanfile,
                                       reference=pref.ref, package_id=pref.id)
        except Exception as exc:
            self._output.writeln("")
            self._output.error("Package '%s' build failed" % pref.id)
            self._output.warn("Build folder %s" % build_folder)
            if isinstance(exc, ConanExceptionInUserConanfileMethod):
                raise exc
            raise ConanException(exc)
        finally:
            # Now remove all files that were imported with imports()
            remove_imports(conanfile, copied_files, self._output)

    def _package(self, conanfile, pref, package_layout, conanfile_path, build_folder,
                 package_folder):
        # FIXME: Is weak to assign here the recipe_hash
        manifest = package_layout.recipe_manifest()
        conanfile.info.recipe_hash = manifest.summary_hash

        # Creating ***info.txt files
        save(os.path.join(build_folder, CONANINFO), conanfile.info.dumps())
        self._output.info("Generated %s" % CONANINFO)
        save(os.path.join(build_folder, BUILD_INFO), TXTGenerator(conanfile).content)
        self._output.info("Generated %s" % BUILD_INFO)

        package_id = pref.id
        # Do the actual copy, call the conanfile.package() method
        with get_env_context_manager(conanfile):
            # Could be source or build depends no_copy_source
            source_folder = conanfile.source_folder
            install_folder = build_folder  # While installing, the infos goes to build folder
            create_package(conanfile, package_id, source_folder, build_folder,
                           package_folder, install_folder, self._hook_manager,
                           conanfile_path, pref.ref)

        # Update package metadata
        package_hash = package_layout.package_summary_hash(pref)
        self._output.info("Created package revision %s" % package_hash)
        with package_layout.update_metadata() as metadata:
            metadata.packages[package_id].revision = package_hash
            metadata.packages[package_id].recipe_revision = pref.ref.revision

        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(package_folder)
        # FIXME: Conan 2.0 Clear the registry entry (package ref)
        return package_hash

    def build_package(self, node, keep_build, recorder):
        t1 = time.time()

        conanfile = node.conanfile
        pref = node.pref

        package_layout = self._cache.package_layout(pref.ref, conanfile.short_paths)
        source_folder = package_layout.source()
        conanfile_path = package_layout.conanfile()
        package_folder = package_layout.package(pref)

        build_folder, skip_build = self._get_build_folder(conanfile, package_layout,
                                                          pref, keep_build, recorder)
        # PREPARE SOURCES
        if not skip_build:
            with package_layout.conanfile_write_lock(self._output):
                set_dirty(build_folder)
                self._prepare_sources(conanfile, pref, package_layout, conanfile_path, source_folder,
                                      build_folder, package_folder)

        # BUILD & PACKAGE
        with package_layout.conanfile_read_lock(self._output):
            mkdir(build_folder)
            os.chdir(build_folder)
            self._output.info('Building your package in %s' % build_folder)
            try:
                if getattr(conanfile, 'no_copy_source', False):
                    conanfile.source_folder = source_folder
                else:
                    conanfile.source_folder = build_folder

                if not skip_build:
                    with get_env_context_manager(conanfile):
                        conanfile.build_folder = build_folder
                        conanfile.package_folder = package_folder
                        # In local cache, install folder always is build_folder
                        conanfile.install_folder = build_folder
                        self._build(conanfile, pref, build_folder)
                    clean_dirty(build_folder)

                prev = self._package(conanfile, pref, package_layout, conanfile_path, build_folder,
                                     package_folder)
                node.prev = prev
                log_file = os.path.join(build_folder, RUN_LOG_NAME)
                log_file = log_file if os.path.exists(log_file) else None
                log_package_built(pref, time.time() - t1, log_file)
                recorder.package_built(pref)
            except ConanException as exc:
                recorder.package_install_error(pref, INSTALL_ERROR_BUILDING,
                                               str(exc), remote_name=None)
                raise exc

            return node.pref


def _handle_system_requirements(conan_file, pref, cache, out):
    """ check first the system_reqs/system_requirements.txt existence, if not existing
    check package/sha1/

    Used after remote package retrieving and before package building
    """
    if "system_requirements" not in type(conan_file).__dict__:
        return

    system_reqs_path = cache.system_reqs(pref.ref)
    system_reqs_package_path = cache.system_reqs_package(pref)
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


def raise_package_not_found_error(conan_file, ref, package_id, dependencies, out, recorder):
    settings_text = ", ".join(conan_file.info.full_settings.dumps().splitlines())
    options_text = ", ".join(conan_file.info.full_options.dumps().splitlines())
    dependencies_text = ', '.join(dependencies)

    msg = '''Can't find a '%s' package for the specified settings, options and dependencies:
- Settings: %s
- Options: %s
- Dependencies: %s
- Package ID: %s
''' % (ref, settings_text, options_text, dependencies_text, package_id)
    out.warn(msg)
    recorder.package_install_error(PackageReference(ref, package_id), INSTALL_ERROR_MISSING, msg)
    raise ConanException('''Missing prebuilt package for '%s'
Try to build it from sources with "--build %s"
Or read "http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package"
''' % (ref, ref.name))


class BinaryInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """
    def __init__(self, cache, output, remote_manager, recorder, hook_manager):
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager
        self._registry = cache.registry
        self._recorder = recorder
        self._hook_manager = hook_manager

    def install(self, deps_graph, keep_build=False, graph_info=None):
        # order by levels and separate the root node (ref=None) from the rest
        nodes_by_level = deps_graph.by_levels()
        root_level = nodes_by_level.pop()
        root_node = root_level[0]
        # Get the nodes in order and if we have to build them
        self._build(nodes_by_level, keep_build, root_node, graph_info)

    def _build(self, nodes_by_level, keep_build, root_node, graph_info):
        processed_package_refs = set()
        for level in nodes_by_level:
            for node in level:
                ref, conan_file = node.ref, node.conanfile
                output = conan_file.output
                package_id = node.package_id
                if node.binary == BINARY_MISSING:
                    dependencies = [str(dep.dst) for dep in node.dependencies]
                    raise_package_not_found_error(conan_file, ref, package_id, dependencies,
                                                  out=output, recorder=self._recorder)

                self._propagate_info(node)
                if node.binary == BINARY_EDITABLE:
                    self._handle_node_editable(node, graph_info)
                else:
                    if node.binary == BINARY_SKIP:  # Privates not necessary
                        continue
                    assert ref.revision is not None, "Installer should receive RREV always"
                    _handle_system_requirements(conan_file, node.pref, self._cache, output)
                    self._handle_node_cache(node, keep_build, processed_package_refs)

        # Finally, propagate information to root node (ref=None)
        self._propagate_info(root_node)

    def _node_concurrently_installed(self, node, package_folder):
        if node.binary == BINARY_DOWNLOAD and os.path.exists(package_folder):
            return True
        elif node.binary == BINARY_UPDATE:
            read_manifest = FileTreeManifest.load(package_folder)
            if node.update_manifest == read_manifest:
                return True

    def _handle_node_editable(self, node, graph_info):
        # Get source of information
        package_layout = self._cache.package_layout(node.ref)
        base_path = package_layout.conan()
        self._call_package_info(node.conanfile, package_folder=base_path)

        node.conanfile.cpp_info.filter_empty = False
        # Try with package-provided file
        editable_cpp_info = package_layout.editable_cpp_info()
        if editable_cpp_info:
            editable_cpp_info.apply_to(node.ref,
                                       node.conanfile.cpp_info,
                                       settings=node.conanfile.settings,
                                       options=node.conanfile.options)

            build_folder = editable_cpp_info.folder(node.ref, EditableLayout.BUILD_FOLDER,
                                                    settings=node.conanfile.settings,
                                                    options=node.conanfile.options)
            if build_folder is not None:
                build_folder = os.path.join(base_path, build_folder)
                output = node.conanfile.output
                write_generators(node.conanfile, build_folder, output)
                save(os.path.join(build_folder, CONANINFO), node.conanfile.info.dumps())
                output.info("Generated %s" % CONANINFO)
                graph_info.save(build_folder)
                output.info("Generated graphinfo")
                save(os.path.join(build_folder, BUILD_INFO), TXTGenerator(node.conanfile).content)
                output.info("Generated %s" % BUILD_INFO)
                # Build step might need DLLs, binaries as protoc to generate source files
                # So execute imports() before build, storing the list of copied_files
                copied_files = run_imports(node.conanfile, build_folder)
                report_copied_files(copied_files, output)

    def _handle_node_cache(self, node, keep_build, processed_package_references):
        pref = node.pref
        assert pref.id, "Package-ID without value"

        conan_file = node.conanfile
        output = conan_file.output
        package_folder = self._cache.package(pref, conan_file.short_paths)

        with self._cache.package_lock(pref):
            if pref not in processed_package_references:
                processed_package_references.add(pref)
                if node.binary == BINARY_BUILD:
                    assert node.prev is None, "PREV for %s to be built should be None" % str(pref)
                    set_dirty(package_folder)
                    pref = self._build_package(node, pref, output, keep_build)
                    clean_dirty(package_folder)
                    assert node.prev is not None, "PREV for %s to be built is None" % str(pref)
                    assert pref.revision is not None, "PREV for %s to be built is None" % str(pref)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    assert node.prev, "PREV for %s is None" % str(pref)
                    if not self._node_concurrently_installed(node, package_folder):
                        set_dirty(package_folder)
                        assert pref.revision is not None, "Installer should receive #PREV always"
                        self._remote_manager.get_package(pref, package_folder,
                                                         node.binary_remote, output,
                                                         self._recorder)
                        output.info("Downloaded package revision %s" % pref.revision)
                        self._registry.prefs.set(pref, node.binary_remote.name)
                        clean_dirty(package_folder)
                    else:
                        output.success('Download skipped. Probable concurrent download')
                        log_package_got_from_local_cache(pref)
                        self._recorder.package_fetched_from_cache(pref)
                elif node.binary == BINARY_CACHE:
                    assert node.prev, "PREV for %s is None" % str(pref)
                    output.success('Already installed!')
                    log_package_got_from_local_cache(pref)
                    self._recorder.package_fetched_from_cache(pref)

            # Call the info method
            self._call_package_info(conan_file, package_folder)
            self._recorder.package_cpp_info(pref, conan_file.cpp_info)

    def _build_package(self, node, pref, output, keep_build):
        conanfile = node.conanfile
        assert pref.id, "Package-ID without value"

        # It is necessary to complete the sources of python requires, which might be used
        for python_require in conanfile.python_requires:
            assert python_require.ref.revision is not None, \
                "Installer should receive python_require.ref always"
            complete_recipe_sources(self._remote_manager, self._cache,
                                    conanfile, python_require.ref)

        builder = _PackageBuilder(self._cache, output, self._hook_manager, self._remote_manager)
        pref = builder.build_package(node, keep_build, self._recorder)
        return pref

    @staticmethod
    def _propagate_info(node):
        # Get deps_cpp_info from upstream nodes
        node_order = [n for n in node.public_closure if n.binary != BINARY_SKIP]
        # List sort is stable, will keep the original order of the closure, but prioritize levels
        conan_file = node.conanfile
        for n in node_order:
            if n.build_require:
                conan_file.output.info("Applying build-requirement: %s" % str(n.ref))
            conan_file.deps_cpp_info.update(n.conanfile.cpp_info, n.ref.name)
            conan_file.deps_env_info.update(n.conanfile.env_info, n.ref.name)
            conan_file.deps_user_info[n.ref.name] = n.conanfile.user_info

        # Update the info but filtering the package values that not apply to the subtree
        # of this current node and its dependencies.
        subtree_libnames = [node.ref.name for node in node_order]
        for package_name, env_vars in conan_file._conan_env_values.data.items():
            for name, value in env_vars.items():
                if not package_name or package_name in subtree_libnames or \
                   package_name == conan_file.name:
                    conan_file.info.env_values.add(name, value, package_name)

    @staticmethod
    def _call_package_info(conanfile, package_folder):
        conanfile.cpp_info = CppInfo(package_folder)
        conanfile.cpp_info.version = conanfile.version
        conanfile.cpp_info.description = conanfile.description
        conanfile.env_info = EnvInfo()
        conanfile.user_info = UserInfo()

        # Get deps_cpp_info from upstream nodes
        public_deps = [name for name, req in conanfile.requires.items() if not req.private]
        conanfile.cpp_info.public_deps = public_deps
        # Once the node is build, execute package info, so it has access to the
        # package folder and artifacts
        with pythonpath(conanfile):  # Minimal pythonpath, not the whole context, make it 50% slower
            with tools.chdir(package_folder):
                with conanfile_exception_formatter(str(conanfile), "package_info"):
                    conanfile.package_folder = package_folder
                    conanfile.source_folder = None
                    conanfile.build_folder = None
                    conanfile.install_folder = None
                    conanfile.package_info()
