import os
import time
import shutil
import platform

from conans.client import tools
from conans.model.conan_file import get_env_context_manager
from conans.model.env_info import EnvInfo
from conans.model.user_info import UserInfo
from conans.paths import CONANINFO, BUILD_INFO, RUN_LOG_NAME
from conans.util.files import save, rmdir, mkdir, make_read_only
from conans.model.ref import PackageReference
from conans.util.log import logger
from conans.errors import (ConanException, conanfile_exception_formatter,
                           ConanExceptionInUserConanfileMethod)
from conans.client.packager import create_package
from conans.client.generators import write_generators, TXTGenerator
from conans.model.build_info import CppInfo
from conans.client.output import ScopedOutput
from conans.client.source import config_source
from conans.util.tracer import log_package_built
from conans.util.env_reader import get_env


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

    def __init__(self, conan_file, package_reference, client_cache, output):
        self._client_cache = client_cache
        self._conan_file = conan_file
        self._out = output
        self._package_reference = package_reference
        self._conan_ref = self._package_reference.conan
        self._skip_build = False  # If build_id()

        new_id = build_id(self._conan_file)
        self.build_reference = PackageReference(self._conan_ref, new_id) if new_id else package_reference
        self.build_folder = self._client_cache.build(self.build_reference,
                                                     self._conan_file.short_paths)

    def prepare_build(self):
        if self.build_reference != self._package_reference and \
              os.path.exists(self.build_folder) and hasattr(self._conan_file, "build_id"):
            self._skip_build = True
            return

        # build_id is not caching the build folder, so actually rebuild the package
        _handle_system_requirements(self._conan_file, self._package_reference,
                                    self._client_cache, self._out)
        package_folder = self._client_cache.package(self._package_reference,
                                                    self._conan_file.short_paths)
        src_folder = self._client_cache.source(self._conan_ref, self._conan_file.short_paths)
        export_folder = self._client_cache.export(self._conan_ref)
        export_source_folder = self._client_cache.export_sources(self._conan_ref,
                                                                 self._conan_file.short_paths)

        try:
            rmdir(self.build_folder)
            rmdir(package_folder)
        except OSError as e:
            raise ConanException("%s\n\nCouldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % str(e))

        self._out.info('Building your package in %s' % self.build_folder)
        config_source(export_folder, export_source_folder, src_folder,
                      self._conan_file, self._out)
        self._out.info('Copying sources to build folder')

        if getattr(self._conan_file, 'no_copy_source', False):
            mkdir(self.build_folder)
            self._conan_file.source_folder = src_folder
        else:
            if platform.system() == "Windows" and os.getenv("CONAN_USER_HOME_SHORT") != "None":
                from conans.util.windows import ignore_long_path_files
                ignore = ignore_long_path_files(src_folder, self.build_folder, self._out)
            else:
                ignore = None

            shutil.copytree(src_folder, self.build_folder, symlinks=True, ignore=ignore)
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
        Receives que build_folder because it can change if build_id() method exists"""

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
            source_folder = self._client_cache.source(self._conan_ref,
                                                      self._conan_file.short_paths)
        else:
            source_folder = self.build_folder
        with get_env_context_manager(self._conan_file):
            package_folder = self._client_cache.package(self._package_reference,
                                                        self._conan_file.short_paths)
            install_folder = self.build_folder  # While installing, the infos goes to build folder
            create_package(self._conan_file, source_folder, self.build_folder, package_folder,
                           install_folder, self._out)

        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(package_folder)

    def _build_package(self):
        """ builds the package, creating the corresponding build folder if necessary
        and copying there the contents from the src folder. The code is duplicated
        in every build, as some configure processes actually change the source
        code. Receives the build_folder because it can change if the method build_id() exists
        """
        package_folder = self._client_cache.package(self._package_reference,
                                                    self._conan_file.short_paths)

        os.chdir(self.build_folder)
        self._conan_file.build_folder = self.build_folder
        self._conan_file.package_folder = package_folder
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
            logger.debug("Call conanfile.build() with files in build folder: %s",
                         os.listdir(self.build_folder))
            self._out.highlight("Calling build()")
            with conanfile_exception_formatter(str(self._conan_file), "build"):
                self._conan_file.build()

            self._out.success("Package '%s' built" % self._conan_file.info.package_id())
            self._out.info("Build folder %s" % self.build_folder)
        except Exception as exc:
            self._out.writeln("")
            self._out.error("Package '%s' build failed" % self._conan_file.info.package_id())
            self._out.warn("Build folder %s" % self.build_folder)
            if isinstance(exc, ConanExceptionInUserConanfileMethod):
                raise exc
            raise ConanException(exc)
        finally:
            # Now remove all files that were imported with imports()
            if not getattr(self._conan_file, "keep_imports", False):
                for f in copied_files:
                    try:
                        if f.startswith(self.build_folder):
                            os.remove(f)
                    except OSError:
                        self._out.warn("Unable to remove imported file from build: %s" % f)


def _raise_package_not_found_error(conan_file, conan_ref, package_id, out):
    settings_text = ", ".join(conan_file.info.full_settings.dumps().splitlines())
    options_text = ", ".join(conan_file.info.full_options.dumps().splitlines())

    out.warn('''Can't find a '%s' package for the specified options and settings:
- Settings: %s
- Options: %s
- Package ID: %s
''' % (conan_ref, settings_text, options_text, package_id))

    raise ConanException('''Missing prebuilt package for '%s'
Try to build it from sources with "--build %s"
Or read "http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package"
''' % (conan_ref, conan_ref.name))


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
    except:
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


def call_package_info(conanfile, package_folder):
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
    with tools.chdir(package_folder):
        with conanfile_exception_formatter(str(conanfile), "package_info"):
            conanfile.package_folder = package_folder
            conanfile.source_folder = None
            conanfile.build_folder = None
            conanfile.install_folder = None
            conanfile.package_info()


class ConanInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """
    def __init__(self, client_cache, output, remote_proxy, build_mode, build_requires):
        self._client_cache = client_cache
        self._out = output
        self._remote_proxy = remote_proxy
        self._build_requires = build_requires
        self._build_mode = build_mode
        self._built_packages = set()  # To avoid re-building twice the same package reference

    def install(self, deps_graph, profile_build_requires, keep_build=False):
        """ given a DepsGraph object, build necessary nodes or retrieve them
        """
        t1 = time.time()
        # order by levels and propagate exports as download imports
        nodes_by_level = deps_graph.by_levels()
        logger.debug("Install-Process buildinfo %s", (time.time() - t1))
        t1 = time.time()
        skip_private_nodes = self._compute_private_nodes(deps_graph)
        logger.debug("Install-Process private %s", (time.time() - t1))
        t1 = time.time()
        self._build(nodes_by_level, skip_private_nodes, deps_graph, profile_build_requires, keep_build)
        logger.debug("Install-build %s", (time.time() - t1))

    def _compute_private_nodes(self, deps_graph):
        """ computes a list of nodes that are not required to be built, as they are
        private requirements of already available shared libraries as binaries.

        If the package requiring a private node has an up to date binary package,
        the private node is not retrieved nor built
        """
        skip_nodes = set()  # Nodes that require private packages but are already built
        for node in deps_graph.nodes:
            conan_ref, conanfile = node
            if not [r for r in conanfile.requires.values() if r.private]:
                continue

            if conan_ref:
                build_forced = self._build_mode.forced(conanfile, conan_ref)
                if build_forced:
                    continue

                package_id = conanfile.info.package_id()
                package_reference = PackageReference(conan_ref, package_id)
                check_outdated = self._build_mode.outdated

                if self._remote_proxy.package_available(package_reference,
                                                        conanfile.short_paths,
                                                        check_outdated):
                    skip_nodes.add(node)

        # Get the private nodes
        skippable_private_nodes = deps_graph.private_nodes(skip_nodes)
        return skippable_private_nodes

    def nodes_to_build(self, deps_graph):
        """Called from info command when a build policy is used in build_order parameter"""
        # Get the nodes in order and if we have to build them
        nodes_by_level = deps_graph.by_levels()
        skip_private_nodes = self._compute_private_nodes(deps_graph)
        nodes = self._get_nodes(nodes_by_level, skip_private_nodes)
        return [(PackageReference(conan_ref, package_id), conan_file)
                for conan_ref, package_id, conan_file, build in nodes if build]

    def _build(self, nodes_by_level, skip_private_nodes, deps_graph, profile_build_requires, keep_build):
        """ The build assumes an input of conans ordered by degree, first level
        should be independent from each other, the next-second level should have
        dependencies only to first level conans.
        param nodes_by_level: list of lists [[nodeA, nodeB], [nodeC], [nodeD, ...], ...]

        build_mode => ["*"] if user wrote "--build"
                   => ["hello*", "bye*"] if user wrote "--build hello --build bye"
                   => False if user wrote "never"
                   => True if user wrote "missing"
                   => "outdated" if user wrote "--build outdated"

        """

        inverse = deps_graph.inverse_levels()
        flat = []

        for level in inverse:
            level = sorted(level, key=lambda x: x.conan_ref)
            flat.extend(n for n in level if n not in skip_private_nodes)

        # Get the nodes in order and if we have to build them
        nodes_to_process = self._get_nodes(nodes_by_level, skip_private_nodes)

        for conan_ref, package_id, conan_file, build_needed in nodes_to_process:
            output = ScopedOutput(str(conan_ref), self._out)

            if build_needed and (conan_ref, package_id) not in self._built_packages:
                package_ref = PackageReference(conan_ref, package_id)
                build_allowed = self._build_mode.allowed(conan_file, conan_ref)
                if not build_allowed:
                    _raise_package_not_found_error(conan_file, conan_ref, package_id, output)

                skip_build = conan_file.develop and keep_build
                if skip_build:
                    output.info("Won't be built as specified by --keep-build")
                else:
                    if conan_file.build_policy_missing:
                        output.info("Building package from source as defined by build_policy='missing'")
                    elif self._build_mode.forced(conan_file, conan_ref):
                        output.warn('Forced build from source')

                if not skip_build:
                    self._build_requires.install(conan_ref, conan_file, self,
                                                 profile_build_requires, output)

                t1 = time.time()
                # Assign to node the propagated info
                self._propagate_info(conan_file, conan_ref, flat, deps_graph)
                builder = _ConanPackageBuilder(conan_file, package_ref, self._client_cache, output)

                if skip_build:
                    if not os.path.exists(builder.build_folder):
                        raise ConanException("--keep-build specified, but build folder not found")
                else:
                    with self._client_cache.conanfile_write_lock(conan_ref):
                        self._remote_proxy.get_recipe_sources(conan_ref, conan_file.short_paths)
                        builder.prepare_build()

                with self._client_cache.conanfile_read_lock(conan_ref):
                    with self._client_cache.package_lock(builder.build_reference):
                        if not skip_build:
                            builder.build()
                        builder.package()

                        self._remote_proxy.handle_package_manifest(package_ref, installed=True)
                        package_folder = self._client_cache.package(package_ref, conan_file.short_paths)
                        # Call the info method
                        call_package_info(conan_file, package_folder)

                        # Log build
                        self._log_built_package(conan_file, package_ref, time.time() - t1)
                        self._built_packages.add((conan_ref, package_id))
            else:
                # Get the package, we have a not outdated remote package
                package_ref = None
                if conan_ref:
                    package_ref = PackageReference(conan_ref, package_id)
                    with self._client_cache.package_lock(package_ref):
                        self._get_remote_package(conan_file, package_ref, output)

                # Assign to the node the propagated info
                # (conan_ref could be None if user project, but of course assign the info
                self._propagate_info(conan_file, conan_ref, flat, deps_graph)

                if package_ref:
                    # Call the info method
                    package_folder = self._client_cache.package(package_ref, conan_file.short_paths)
                    call_package_info(conan_file, package_folder)

    def _get_remote_package(self, conan_file, package_reference, output):
        """Get remote package. It won't check if it's outdated"""
        # Compute conan_file package from local (already compiled) or from remote

        package_folder = self._client_cache.package(package_reference,
                                                    conan_file.short_paths)

        # If already exists do not dirt the output, the common situation
        # is that package is already installed and OK. If don't, the proxy
        # will print some other message about it
        if not os.path.exists(package_folder):
            self._out.info("Retrieving package %s" % package_reference.package_id)

        if self._remote_proxy.get_package(package_reference,
                                          short_paths=conan_file.short_paths):
            _handle_system_requirements(conan_file, package_reference,
                                        self._client_cache, output)
            if get_env("CONAN_READ_ONLY_CACHE", False):
                make_read_only(package_folder)
            return True

        _raise_package_not_found_error(conan_file, package_reference.conan,
                                       package_reference.package_id, output)

    def _log_built_package(self, conan_file, package_ref, duration):
        build_folder = self._client_cache.build(package_ref, conan_file.short_paths)
        log_file = os.path.join(build_folder, RUN_LOG_NAME)
        log_file = log_file if os.path.exists(log_file) else None
        log_package_built(package_ref, duration, log_file)

    @staticmethod
    def _propagate_info(conan_file, conan_ref, flat, deps_graph):
        # Get deps_cpp_info from upstream nodes
        node_order = deps_graph.ordered_closure((conan_ref, conan_file), flat)
        for n in node_order:
            conan_file.deps_cpp_info.update(n.conanfile.cpp_info, n.conan_ref.name)
            conan_file.deps_env_info.update(n.conanfile.env_info, n.conan_ref.name)
            conan_file.deps_user_info[n.conan_ref.name] = n.conanfile.user_info

        # Update the info but filtering the package values that not apply to the subtree
        # of this current node and its dependencies.
        subtree_libnames = [ref.name for (ref, _) in node_order]
        for package_name, env_vars in conan_file._env_values.data.items():
            for name, value in env_vars.items():
                if not package_name or package_name in subtree_libnames or \
                   package_name == conan_file.name:
                    conan_file.info.env_values.add(name, value, package_name)

    def _get_nodes(self, nodes_by_level, skip_nodes):
        """Install the available packages if needed/allowed and return a list
        of nodes to build (tuples (conan_file, conan_ref))
        and installed nodes"""

        nodes_to_build = []
        # Now build each level, starting from the most independent one
        package_references = set()
        for level in nodes_by_level:
            for node in level:
                if node in skip_nodes:
                    continue
                conan_ref, conan_file = node

                # it is possible that the root conans
                # is not inside the storage but in a user folder, and thus its
                # treatment is different
                build_node = False
                package_id = None
                if conan_ref:
                    logger.debug("Processing node %s", repr(conan_ref))
                    package_id = conan_file.info.package_id()
                    package_reference = PackageReference(conan_ref, package_id)
                    # Avoid processing twice the same package reference
                    if package_reference not in package_references:
                        package_references.add(package_reference)
                        check_outdated = self._build_mode.outdated
                        if self._build_mode.forced(conan_file, conan_ref):
                            build_node = True
                        else:
                            available = self._remote_proxy.package_available(package_reference,
                                                                             conan_file.short_paths,
                                                                             check_outdated)
                            build_node = not available

                nodes_to_build.append((conan_ref, package_id, conan_file, build_node))

        # A check to be sure that if introduced a pattern, something is going to be built

        if self._build_mode.patterns:
            to_build = [str(n[0].name) for n in nodes_to_build if n[3]]
            self._build_mode.check_matches(to_build)

        return nodes_to_build
