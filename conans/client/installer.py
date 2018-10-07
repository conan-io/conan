import os
import time
import shutil
import platform

from conans.client import tools
from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING_BUILD_FOLDER, INSTALL_ERROR_BUILDING,\
    INSTALL_ERROR_MISSING
from conans.model.conan_file import get_env_context_manager
from conans.model.env_info import EnvInfo
from conans.model.user_info import UserInfo
from conans.paths import CONANINFO, BUILD_INFO, RUN_LOG_NAME
from conans.util.files import (save, rmdir, mkdir, make_read_only,
                               set_dirty, clean_dirty, load)
from conans.model.ref import PackageReference
from conans.util.log import logger
from conans.errors import (ConanException, conanfile_exception_formatter,
                           ConanExceptionInUserConanfileMethod)
from conans.client.packager import create_package
from conans.client.generators import write_generators, TXTGenerator
from conans.model.build_info import CppInfo
from conans.client.output import ScopedOutput
from conans.client.source import config_source, complete_recipe_sources
from conans.util.env_reader import get_env
from conans.client.importer import remove_imports

from conans.util.tracer import log_package_built,\
    log_package_got_from_local_cache
from conans.client.tools.env import pythonpath
from conans.client.graph.graph import BINARY_SKIP, BINARY_MISSING,\
    BINARY_DOWNLOAD, BINARY_UPDATE, BINARY_BUILD, BINARY_CACHE
from conans.client.file_copier import report_copied_files


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


class _ConanPackageBuilder(object):
    """Builds and packages a single conan_file binary package"""

    def __init__(self, conan_file, package_reference, client_cache, output, plugin_manager):
        self._client_cache = client_cache
        self._conan_file = conan_file
        self._out = output
        self._package_reference = package_reference
        self._conan_ref = self._package_reference.conan
        self._skip_build = False  # If build_id()
        self._plugin_manager = plugin_manager

        new_id = build_id(self._conan_file)
        self.build_reference = PackageReference(self._conan_ref,
                                                new_id) if new_id else package_reference
        self.build_folder = self._client_cache.build(self.build_reference,
                                                     self._conan_file.short_paths)
        self.package_folder = self._client_cache.package(self._package_reference,
                                                         self._conan_file.short_paths)
        self.source_folder = self._client_cache.source(self._conan_ref, self._conan_file.short_paths)

    def prepare_build(self):
        if self.build_reference != self._package_reference and \
              os.path.exists(self.build_folder) and hasattr(self._conan_file, "build_id"):
            self._skip_build = True
            return

        # build_id is not caching the build folder, so actually rebuild the package
        export_folder = self._client_cache.export(self._conan_ref)
        export_source_folder = self._client_cache.export_sources(self._conan_ref,
                                                                 self._conan_file.short_paths)
        conanfile_path = self._client_cache.conanfile(self._conan_ref)

        try:
            rmdir(self.build_folder)
            rmdir(self.package_folder)
        except OSError as e:
            raise ConanException("%s\n\nCouldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % str(e))

        self._out.info('Building your package in %s' % self.build_folder)
        sources_pointer = self._client_cache.scm_folder(self._conan_ref)
        local_sources_path = load(sources_pointer) if os.path.exists(sources_pointer) else None
        config_source(export_folder, export_source_folder, local_sources_path, self.source_folder,
                      self._conan_file, self._out, conanfile_path, self._conan_ref,
                      self._plugin_manager)
        self._out.info('Copying sources to build folder')

        if getattr(self._conan_file, 'no_copy_source', False):
            mkdir(self.build_folder)
            self._conan_file.source_folder = self.source_folder
        else:
            if platform.system() == "Windows" and os.getenv("CONAN_USER_HOME_SHORT") != "None":
                from conans.util.windows import ignore_long_path_files
                ignore = ignore_long_path_files(self.source_folder, self.build_folder, self._out)
            else:
                ignore = None

            shutil.copytree(self.source_folder, self.build_folder, symlinks=True, ignore=ignore)
            logger.debug("Copied to %s", self.build_folder)
            logger.debug("Files copied %s", os.listdir(self.build_folder))
            self._conan_file.source_folder = self.build_folder

    def build(self):
        """Calls the conanfile's build method"""
        if self._skip_build:
            return
        with get_env_context_manager(self._conan_file):
            self._build_package()

    def package(self):
        """Generate the info txt files and calls the conanfile package method.
        """

        # FIXME: Is weak to assign here the recipe_hash
        manifest = self._client_cache.load_manifest(self._conan_ref)
        self._conan_file.info.recipe_hash = manifest.summary_hash

        # Creating ***info.txt files
        save(os.path.join(self.build_folder, CONANINFO), self._conan_file.info.dumps())
        self._out.info("Generated %s" % CONANINFO)
        save(os.path.join(self.build_folder, BUILD_INFO), TXTGenerator(self._conan_file).content)
        self._out.info("Generated %s" % BUILD_INFO)

        os.chdir(self.build_folder)

        if getattr(self._conan_file, 'no_copy_source', False):
            source_folder = self.source_folder
        else:
            source_folder = self.build_folder
        with get_env_context_manager(self._conan_file):
            install_folder = self.build_folder  # While installing, the infos goes to build folder
            pkg_id = self._conan_file.info.package_id()
            conanfile_path = self._client_cache.conanfile(self._conan_ref)

            create_package(self._conan_file, pkg_id, source_folder, self.build_folder,
                           self.package_folder, install_folder, self._out, self._plugin_manager,
                           conanfile_path, self._conan_ref)

        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(self.package_folder)

    def _build_package(self):
        """ calls the imports + conanfile.build() method
        """
        os.chdir(self.build_folder)
        self._conan_file.build_folder = self.build_folder
        self._conan_file.package_folder = self.package_folder
        # In local cache, install folder always is build_folder
        self._conan_file.install_folder = self.build_folder

        # Read generators from conanfile and generate the needed files
        logger.debug("Writing generators")
        write_generators(self._conan_file, self.build_folder, self._out)
        logger.debug("Files copied after generators %s", os.listdir(self.build_folder))

        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files
        from conans.client.importer import run_imports
        copied_files = run_imports(self._conan_file, self.build_folder, self._out)

        try:
            # This is necessary because it is different for user projects
            # than for packages
            self._plugin_manager.execute("pre_build", conanfile=self._conan_file,
                                         reference=self._conan_ref,
                                         package_id=self._package_reference.package_id)
            logger.debug("Call conanfile.build() with files in build folder: %s",
                         os.listdir(self.build_folder))
            self._out.highlight("Calling build()")
            with conanfile_exception_formatter(str(self._conan_file), "build"):
                self._conan_file.build()

            self._out.success("Package '%s' built" % self._conan_file.info.package_id())
            self._out.info("Build folder %s" % self.build_folder)
            self._plugin_manager.execute("post_build", conanfile=self._conan_file,
                                         reference=self._conan_ref,
                                         package_id=self._package_reference.package_id)
        except Exception as exc:
            self._out.writeln("")
            self._out.error("Package '%s' build failed" % self._conan_file.info.package_id())
            self._out.warn("Build folder %s" % self.build_folder)
            if isinstance(exc, ConanExceptionInUserConanfileMethod):
                raise exc
            raise ConanException(exc)
        finally:
            # Now remove all files that were imported with imports()
            remove_imports(self._conan_file, copied_files, self._out)


def _handle_system_requirements(conan_file, package_reference, client_cache, out):
    """ check first the system_reqs/system_requirements.txt existence, if not existing
    check package/sha1/

    Used after remote package retrieving and before package building
    """
    if "system_requirements" not in type(conan_file).__dict__:
        return

    system_reqs_path = client_cache.system_reqs(package_reference.conan)
    system_reqs_package_path = client_cache.system_reqs_package(package_reference)
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


def raise_package_not_found_error(conan_file, conan_ref, package_id, dependencies, out, recorder):
    settings_text = ", ".join(conan_file.info.full_settings.dumps().splitlines())
    options_text = ", ".join(conan_file.info.full_options.dumps().splitlines())
    dependencies_text = ', '.join(dependencies)

    msg = '''Can't find a '%s' package for the specified settings, options and dependencies:
- Settings: %s
- Options: %s
- Dependencies: %s
- Package ID: %s
''' % (conan_ref, settings_text, options_text, dependencies_text, package_id)
    out.warn(msg)
    recorder.package_install_error(PackageReference(conan_ref, package_id),
                                   INSTALL_ERROR_MISSING, msg)
    raise ConanException('''Missing prebuilt package for '%s'
Try to build it from sources with "--build %s"
Or read "http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package"
''' % (conan_ref, conan_ref.name))


class ConanInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """
    def __init__(self, client_cache, output, remote_manager, registry, recorder, workspace,
                 plugin_manager):
        self._client_cache = client_cache
        self._out = output
        self._remote_manager = remote_manager
        self._registry = registry
        self._recorder = recorder
        self._workspace = workspace
        self._plugin_manager = plugin_manager

    def install(self, deps_graph, keep_build=False):
        # order by levels and separate the root node (conan_ref=None) from the rest
        nodes_by_level = deps_graph.by_levels()
        root_level = nodes_by_level.pop()
        root_node = root_level[0]
        # Get the nodes in order and if we have to build them
        self._build(nodes_by_level, deps_graph, keep_build, root_node)

    def _build(self, nodes_by_level, deps_graph, keep_build, root_node):
        inverse_levels = {n: i for i, level in enumerate(deps_graph.inverse_levels()) for n in level}

        processed_package_refs = set()
        for level in nodes_by_level:
            for node in level:
                conan_ref, conan_file = node.conan_ref, node.conanfile
                output = ScopedOutput(str(conan_ref), self._out)
                package_id = conan_file.info.package_id()
                if node.binary == BINARY_MISSING:
                    dependencies = [str(dep.dst) for dep in node.dependencies]
                    raise_package_not_found_error(conan_file, conan_ref, package_id, dependencies,
                                                  out=output, recorder=self._recorder)

                self._propagate_info(node, inverse_levels, deps_graph, output)
                if node.binary == BINARY_SKIP:  # Privates not necessary
                    continue

                workspace_package = self._workspace[node.conan_ref] if self._workspace else None
                if workspace_package:
                    self._handle_node_workspace(node, workspace_package, inverse_levels, deps_graph)
                else:
                    package_ref = PackageReference(conan_ref, package_id)
                    _handle_system_requirements(conan_file, package_ref, self._client_cache, output)
                    self._handle_node_cache(node, package_ref, keep_build, processed_package_refs)

        # Finally, propagate information to root node (conan_ref=None)
        self._propagate_info(root_node, inverse_levels, deps_graph, self._out)

    def _handle_node_cache(self, node, package_ref, keep_build, processed_package_references):
        conan_ref, conan_file = node.conan_ref, node.conanfile
        output = ScopedOutput(str(conan_ref), self._out)
        package_folder = self._client_cache.package(package_ref, conan_file.short_paths)

        with self._client_cache.package_lock(package_ref):
            if package_ref not in processed_package_references:
                processed_package_references.add(package_ref)
                set_dirty(package_folder)
                if node.binary == BINARY_BUILD:
                    self._build_package(node, package_ref, output, keep_build)
                elif node.binary in (BINARY_UPDATE, BINARY_DOWNLOAD):
                    self._remote_manager.get_package(package_ref, package_folder,
                                                     node.binary_remote, output, self._recorder)
                    if node.binary_remote != node.remote:
                        self._registry.set_ref(conan_ref, node.binary_remote.name)
                elif node.binary == BINARY_CACHE:
                    output.success('Already installed!')
                    log_package_got_from_local_cache(package_ref)
                    self._recorder.package_fetched_from_cache(package_ref)
                clean_dirty(package_folder)
            # Call the info method
            self._call_package_info(conan_file, package_folder)

    def _handle_node_workspace(self, node, workspace_package, inverse_levels, deps_graph):
        conan_ref, conan_file = node.conan_ref, node.conanfile
        output = ScopedOutput("Workspace %s" % conan_ref.name, self._out)
        include_dirs = workspace_package.includedirs
        lib_dirs = workspace_package.libdirs
        self._call_package_info(conan_file, workspace_package.package_folder)
        if include_dirs:
            conan_file.cpp_info.includedirs = include_dirs
        if lib_dirs:
            conan_file.cpp_info.libdirs = lib_dirs
            # Make sure the folders exists, otherwise they will be filtered out
            lib_paths = [os.path.join(conan_file.cpp_info.rootpath, p)
                         if not os.path.isabs(p) else p for p in lib_dirs]
            for p in lib_paths:
                mkdir(p)

        self._propagate_info(node, inverse_levels, deps_graph, output)

        build_folder = workspace_package.build_folder
        write_generators(conan_file, build_folder, output)
        save(os.path.join(build_folder, CONANINFO), conan_file.info.dumps())
        output.info("Generated %s" % CONANINFO)
        save(os.path.join(build_folder, BUILD_INFO), TXTGenerator(conan_file).content)
        output.info("Generated %s" % BUILD_INFO)
        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files
        from conans.client.importer import run_imports
        copied_files = run_imports(conan_file, build_folder, output)
        report_copied_files(copied_files, output)

    def _build_package(self, node, package_ref, output, keep_build):
        conan_ref, conan_file = node.conan_ref, node.conanfile

        skip_build = conan_file.develop and keep_build
        if skip_build:
            output.info("Won't be built as specified by --keep-build")

        t1 = time.time()
        builder = _ConanPackageBuilder(conan_file, package_ref, self._client_cache, output,
                                       self._plugin_manager)

        if skip_build:
            if not os.path.exists(builder.build_folder):
                msg = "--keep-build specified, but build folder not found"
                self._recorder.package_install_error(package_ref,
                                                     INSTALL_ERROR_MISSING_BUILD_FOLDER,
                                                     msg, remote_name=None)
                raise ConanException(msg)
        else:
            with self._client_cache.conanfile_write_lock(conan_ref):
                complete_recipe_sources(self._remote_manager, self._client_cache,
                                        self._registry, conan_file, conan_ref)
                builder.prepare_build()

        with self._client_cache.conanfile_read_lock(conan_ref):
            try:
                if not skip_build:
                    builder.build()
                builder.package()
            except ConanException as exc:
                self._recorder.package_install_error(package_ref, INSTALL_ERROR_BUILDING,
                                                     str(exc), remote_name=None)
                raise exc
            else:
                # Log build
                self._log_built_package(builder.build_folder, package_ref, time.time() - t1)

    def _log_built_package(self, build_folder, package_ref, duration):
        log_file = os.path.join(build_folder, RUN_LOG_NAME)
        log_file = log_file if os.path.exists(log_file) else None
        log_package_built(package_ref, duration, log_file)
        self._recorder.package_built(package_ref)

    @staticmethod
    def _propagate_info(node, inverse_levels, deps_graph, out):
        # Get deps_cpp_info from upstream nodes
        closure = deps_graph.full_closure(node)
        node_order = [n for n in closure.values() if n.binary != BINARY_SKIP]
        # List sort is stable, will keep the original order of the closure, but prioritize levels
        node_order.sort(key=lambda n: inverse_levels[n])

        conan_file = node.conanfile
        for n in node_order:
            if n.build_require:
                out.info("Applying build-requirement: %s" % str(n.conan_ref))
            conan_file.deps_cpp_info.update(n.conanfile.cpp_info, n.conan_ref.name)
            conan_file.deps_env_info.update(n.conanfile.env_info, n.conan_ref.name)
            conan_file.deps_user_info[n.conan_ref.name] = n.conanfile.user_info

        # Update the info but filtering the package values that not apply to the subtree
        # of this current node and its dependencies.
        subtree_libnames = [node.conan_ref.name for node in node_order]
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
