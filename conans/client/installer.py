import os
import time
import platform
import fnmatch
import shutil

from conans.paths import CONANINFO, BUILD_INFO, CONANENV, RUN_LOG_NAME, CONANFILE
from conans.util.files import save, rmdir, mkdir
from conans.model.ref import PackageReference
from conans.util.log import logger
from conans.errors import ConanException, conanfile_exception_formatter
from conans.client.packager import create_package
from conans.client.generators import write_generators, TXTGenerator
from conans.model.build_info import CppInfo
from conans.client.output import ScopedOutput
from conans.model.env_info import EnvInfo
from conans.client.source import config_source
from conans.client.generators.env import ConanEnvGenerator
from conans.tools import environment_append
from conans.util.tracer import log_package_built


def _init_package_info(deps_graph, paths, current_path):
    for node in deps_graph.nodes:
        conan_ref, conan_file = node
        if conan_ref:
            package_id = conan_file.info.package_id()
            package_reference = PackageReference(conan_ref, package_id)
            package_folder = paths.package(package_reference, conan_file.short_paths)
            conan_file.package_folder = package_folder
            conan_file.cpp_info = CppInfo(package_folder)
            conan_file.env_info = EnvInfo(package_folder)
        else:
            conan_file.cpp_info = CppInfo(current_path)
            conan_file.env_info = EnvInfo(current_path)


def build_id(conanfile):
    if hasattr(conanfile, "build_id"):
        # construct new ConanInfo
        build_id_info = conanfile.info.copy()
        conanfile.info_build = build_id_info
        # effectively call the user function to change the package values
        with conanfile_exception_formatter(str(conanfile), "build_id"):
            conanfile.build_id()
        # compute modified ID
        return build_id_info.package_id()
    return None


class BuildMode(object):
    def __init__(self, params, output):
        self._out = output
        self.outdated = False
        self.missing = False
        self.patterns = []
        self._unused_patterns = []
        self.all = False
        if params is None:
            return

        assert isinstance(params, list)
        if len(params) == 0:
            self.all = True
        else:
            never = False
            for param in params:
                if param == "outdated":
                    self.outdated = True
                elif param == "missing":
                    self.missing = True
                elif param == "never":
                    never = True
                else:
                    self.patterns.append("%s*" % param)

            if never and (self.outdated or self.missing or self.patterns):
                raise ConanException("--build=never not compatible with other options")
        self._unused_patterns = list(self.patterns)

    def forced(self, reference, conanfile):
        if self.all:
            return True

        ref = str(reference)
        if conanfile.build_policy_always:
            out = ScopedOutput(ref, self._out)
            out.info("Building package from source as defined by build_policy='always'")
            return True

        # Patterns to match, if package matches pattern, build is forced
        force_build = any([fnmatch.fnmatch(ref, pattern) for pattern in self.patterns])
        return force_build

    def allowed(self, reference, conanfile):
        return (self.missing or self.outdated or self.forced(reference, conanfile) or
                conanfile.build_policy_missing)

    def check_matches(self, references):
        for pattern in list(self._unused_patterns):
            matched = any(fnmatch.fnmatch(ref, pattern) for ref in references)
            if matched:
                self._unused_patterns.remove(pattern)

    def report_matches(self):
        for pattern in self._unused_patterns:
            self._out.error("No package matching '%s' pattern" % pattern)


class ConanInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """
    def __init__(self, client_cache, output, remote_proxy, build_requires):

        self._client_cache = client_cache
        self._out = output
        self._remote_proxy = remote_proxy
        self._build_requires = build_requires

    def install(self, deps_graph, build_mode, current_path):
        """ given a DepsGraph object, build necessary nodes or retrieve them
        """
        self._deps_graph = deps_graph  # necessary for _build_package
        t1 = time.time()
        _init_package_info(deps_graph, self._client_cache, current_path)
        # order by levels and propagate exports as download imports
        nodes_by_level = deps_graph.by_levels()
        logger.debug("Install-Process buildinfo %s" % (time.time() - t1))
        t1 = time.time()
        skip_private_nodes = self._compute_private_nodes(deps_graph, build_mode)
        logger.debug("Install-Process private %s" % (time.time() - t1))
        t1 = time.time()
        self._build(nodes_by_level, skip_private_nodes, build_mode)
        logger.debug("Install-build %s" % (time.time() - t1))

    def _compute_private_nodes(self, deps_graph, build_mode):
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
                build_forced = build_mode.forced(conan_ref, conanfile)
                if build_forced:
                    continue

                package_id = conanfile.info.package_id()
                package_reference = PackageReference(conan_ref, package_id)
                check_outdated = build_mode.outdated

                if self._remote_proxy.package_available(package_reference,
                                                        conanfile.short_paths,
                                                        check_outdated):
                    skip_nodes.add(node)

        # Get the private nodes
        skippable_private_nodes = deps_graph.private_nodes(skip_nodes)
        return skippable_private_nodes

    def nodes_to_build(self, deps_graph, build_mode):
        """Called from info command when a build policy is used in build_order parameter"""
        # Get the nodes in order and if we have to build them
        nodes_by_level = deps_graph.by_levels()
        skip_private_nodes = self._compute_private_nodes(deps_graph, build_mode)
        nodes = self._get_nodes(nodes_by_level, skip_private_nodes, build_mode)
        return [(PackageReference(conan_ref, package_id), conan_file)
                for conan_ref, package_id, conan_file, build in nodes if build]

    def _build(self, nodes_by_level, skip_private_nodes, build_mode):
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

        inverse = self._deps_graph.inverse_levels()
        flat = []

        for level in inverse:
            level = sorted(level, key=lambda x: x.conan_ref)
            flat.extend(level)

        # Get the nodes in order and if we have to build them
        nodes_to_process = self._get_nodes(nodes_by_level, skip_private_nodes, build_mode)

        for conan_ref, package_id, conan_file, build_needed in nodes_to_process:

            if build_needed:
                build_allowed = build_mode.allowed(conan_ref, conan_file)
                if not build_allowed:
                    self._raise_package_not_found_error(conan_ref, conan_file)

                output = ScopedOutput(str(conan_ref), self._out)
                package_ref = PackageReference(conan_ref, package_id)
                package_folder = self._client_cache.package(package_ref, conan_file.short_paths)
                if conan_file.build_policy_missing:
                    output.info("Building package from source as defined by build_policy='missing'")
                elif build_mode.forced(conan_ref, conan_file):
                    output.warn('Forced build from source')

                self._build_requires.install(conan_ref, conan_file)

                t1 = time.time()
                # Assign to node the propagated info
                self._propagate_info(conan_ref, conan_file, flat)

                self._remote_proxy.get_recipe_sources(conan_ref)
                # Call the conanfile's build method
                build_folder = self._build_conanfile(conan_ref, conan_file, package_ref,
                                                     package_folder, output)

                # Call the conanfile's package method
                self._package_conanfile(conan_ref, conan_file, package_ref, build_folder,
                                        package_folder, output)

                # Call the info method
                self._package_info_conanfile(conan_ref, conan_file)

                duration = time.time() - t1
                log_file = os.path.join(build_folder, RUN_LOG_NAME)
                log_file = log_file if os.path.exists(log_file) else None
                log_package_built(package_ref, duration, log_file)
            else:
                # Get the package, we have a not outdated remote package
                if conan_ref:
                    self._get_package(conan_ref, conan_file)

                # Assign to the node the propagated info
                # (conan_ref could be None if user project, but of course assign the info
                self._propagate_info(conan_ref, conan_file, flat)

                # Call the info method
                self._package_info_conanfile(conan_ref, conan_file)

    def _propagate_info(self, conan_ref, conan_file, flat):
        # Get deps_cpp_info from upstream nodes
        node_order = self._deps_graph.ordered_closure((conan_ref, conan_file), flat)
        public_deps = [name for name, req in conan_file.requires.items() if not req.private]
        conan_file.cpp_info.public_deps = public_deps
        for n in node_order:
            conan_file.deps_cpp_info.update(n.conanfile.cpp_info, n.conan_ref.name)
            conan_file.deps_env_info.update(n.conanfile.env_info, n.conan_ref.name)

        # Update the env_values with the inherited from dependencies
        conan_file._env_values.update(conan_file.deps_env_info)

        # Update the info but filtering the package values that not apply to the subtree
        # of this current node and its dependencies.
        subtree_libnames = [ref.name for (ref, _) in node_order]
        for package_name, env_vars in conan_file._env_values.data.items():
            for name, value in env_vars.items():
                if not package_name or package_name in subtree_libnames or package_name == conan_file.name:
                    conan_file.info.env_values.add(name, value, package_name)

    def _get_nodes(self, nodes_by_level, skip_nodes, build_mode):
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
                    logger.debug("Processing node %s" % repr(conan_ref))
                    package_id = conan_file.info.package_id()
                    package_reference = PackageReference(conan_ref, package_id)
                    # Avoid processing twice the same package reference
                    if package_reference not in package_references:
                        package_references.add(package_reference)
                        check_outdated = build_mode.outdated
                        if build_mode.forced(conan_ref, conan_file):
                            build_node = True
                        else:
                            build_node = not self._remote_proxy.package_available(package_reference,
                                                                                  conan_file.short_paths,
                                                                                  check_outdated)

                nodes_to_build.append((conan_ref, package_id, conan_file, build_node))

        # A check to be sure that if introduced a pattern, something is going to be built

        if build_mode.patterns:
            to_build = [str(n[0]) for n in nodes_to_build if n[3]]
            build_mode.check_matches(to_build)

        return nodes_to_build

    def _get_package(self, conan_ref, conan_file):
        '''Get remote package. It won't check if it's outdated'''
        # Compute conan_file package from local (already compiled) or from remote
        output = ScopedOutput(str(conan_ref), self._out)
        package_id = conan_file.info.package_id()
        package_reference = PackageReference(conan_ref, package_id)

        conan_ref = package_reference.conan
        package_folder = self._client_cache.package(package_reference, conan_file.short_paths)

        # If already exists do not dirt the output, the common situation
        # is that package is already installed and OK. If don't, the proxy
        # will print some other message about it
        if not os.path.exists(package_folder):
            output.info("Installing package %s" % package_id)

        if self._remote_proxy.get_package(package_reference, short_paths=conan_file.short_paths):
            self._handle_system_requirements(conan_ref, package_reference, conan_file, output)
            return True

        self._raise_package_not_found_error(conan_ref, conan_file)

    def _build_conanfile(self, conan_ref, conan_file, package_reference, package_folder, output):
        """Calls the conanfile's build method"""
        new_id = build_id(conan_file)
        if new_id:
            package_reference = PackageReference(package_reference.conan, new_id)
        build_folder = self._client_cache.build(package_reference, conan_file.short_paths)
        if os.path.exists(build_folder) and hasattr(conan_file, "build_id"):
            return build_folder
        # build_id is not caching the build folder, so actually rebuild the package
        src_folder = self._client_cache.source(conan_ref, conan_file.short_paths)
        export_folder = self._client_cache.export(conan_ref)

        self._handle_system_requirements(conan_ref, package_reference, conan_file, output)
        with environment_append(conan_file.env):
            self._build_package(export_folder, src_folder, build_folder, package_folder, conan_file, output)
        return build_folder

    def _package_conanfile(self, conan_ref, conan_file, package_reference, build_folder,
                           package_folder, output):
        """Generate the info txt files and calls the conanfile package method"""

        # FIXME: Is weak to assign here the recipe_hash
        conan_file.info.recipe_hash = self._client_cache.load_manifest(conan_ref).summary_hash

        # Creating ***info.txt files
        save(os.path.join(build_folder, CONANINFO), conan_file.info.dumps())
        output.info("Generated %s" % CONANINFO)
        save(os.path.join(build_folder, BUILD_INFO), TXTGenerator(conan_file).content)
        output.info("Generated %s" % BUILD_INFO)
        save(os.path.join(build_folder, CONANENV), ConanEnvGenerator(conan_file).content)
        output.info("Generated %s" % CONANENV)

        os.chdir(build_folder)

        if getattr(conan_file, 'no_copy_source', False):
            source_folder = self._client_cache.source(package_reference.conan,
                                                      conan_file.short_paths)
        else:
            source_folder = build_folder
        with environment_append(conan_file.env):
            create_package(conan_file, source_folder, build_folder, package_folder, output, False)
            self._remote_proxy.handle_package_manifest(package_reference, installed=True)

    def _raise_package_not_found_error(self, conan_ref, conan_file):
        settings_text = ", ".join(conan_file.info.full_settings.dumps().splitlines())
        options_text = ", ".join(conan_file.info.full_options.dumps().splitlines())

        self._out.warn('''Can't find a '%s' package for the specified options and settings:
- Settings: %s
- Options: %s
''' % (conan_ref, settings_text, options_text))

        raise ConanException('''Missing prebuilt package for '%s'
Try to build it from sources with "--build %s"
Or read "http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package"
''' % (conan_ref, conan_ref.name))

    def _handle_system_requirements(self, conan_ref, package_reference, conan_file, coutput):
        """ check first the system_reqs/system_requirements.txt existence, if not existing
        check package/sha1/
        """
        if "system_requirements" not in type(conan_file).__dict__:
            return

        system_reqs_path = self._client_cache.system_reqs(conan_ref)
        system_reqs_package_path = self._client_cache.system_reqs_package(package_reference)
        if os.path.exists(system_reqs_path) or os.path.exists(system_reqs_package_path):
            return

        output = self.call_system_requirements(conan_file, coutput)

        try:
            output = str(output or "")
        except:
            coutput.warn("System requirements didn't return a string")
            output = ""
        if getattr(conan_file, "global_system_requirements", None):
            save(system_reqs_path, output)
        else:
            save(system_reqs_package_path, output)

    def call_system_requirements(self, conan_file, output):
        try:
            return conan_file.system_requirements()
        except Exception as e:
            output.error("while executing system_requirements(): %s" % str(e))
            raise ConanException("Error in system requirements")

    def _build_package(self, export_folder, src_folder, build_folder, package_folder, conan_file, output):
        """ builds the package, creating the corresponding build folder if necessary
        and copying there the contents from the src folder. The code is duplicated
        in every build, as some configure processes actually change the source
        code
        """

        try:
            rmdir(build_folder)
            rmdir(package_folder)
        except Exception as e:
            raise ConanException("%s\n\nCouldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % str(e))

        output.info('Building your package in %s' % build_folder)
        config_source(export_folder, src_folder, conan_file, output)
        output.info('Copying sources to build folder')

        def check_max_path_len(src, files):
            if platform.system() != "Windows":
                return []
            filtered_files = []
            for the_file in files:
                source_path = os.path.join(src, the_file)
                # Without storage path, just relative
                rel_path = os.path.relpath(source_path, src_folder)
                dest_path = os.path.normpath(os.path.join(build_folder, rel_path))
                # it is NOT that "/" is counted as "\\" so it counts double
                # seems a bug in python, overflows paths near the limit of 260,
                if len(dest_path) >= 249:
                    filtered_files.append(the_file)
                    output.warn("Filename too long, file excluded: %s" % dest_path)
            return filtered_files

        if getattr(conan_file, 'no_copy_source', False):
            mkdir(build_folder)
            conan_file.source_folder = src_folder
        else:
            shutil.copytree(src_folder, build_folder, symlinks=True, ignore=check_max_path_len)
            logger.debug("Copied to %s" % build_folder)
            logger.debug("Files copied %s" % os.listdir(build_folder))
            conan_file.source_folder = build_folder

        os.chdir(build_folder)
        conan_file.build_folder = build_folder
        conan_file._conanfile_directory = build_folder
        # Read generators from conanfile and generate the needed files
        logger.debug("Writing generators")
        write_generators(conan_file, build_folder, output)
        logger.debug("Files copied after generators %s" % os.listdir(build_folder))

        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files
        from conans.client.importer import run_imports
        copied_files = run_imports(conan_file, build_folder, output)

        try:
            # This is necessary because it is different for user projects
            # than for packages
            logger.debug("Call conanfile.build() with files in build folder: %s" % os.listdir(build_folder))
            with conanfile_exception_formatter(str(conan_file), "build"):
                conan_file.build()

            self._out.writeln("")
            output.success("Package '%s' built" % conan_file.info.package_id())
            output.info("Build folder %s" % build_folder)
        except Exception as exc:
            os.chdir(src_folder)
            self._out.writeln("")
            output.error("Package '%s' build failed" % conan_file.info.package_id())
            output.warn("Build folder %s" % build_folder)
            raise exc
        finally:
            conan_file._conanfile_directory = export_folder
            # Now remove all files that were imported with imports()
            for f in copied_files:
                try:
                    if(f.startswith(build_folder)):
                        os.remove(f)
                except Exception:
                    self._out.warn("Unable to remove imported file from build: %s" % f)

    def _package_info_conanfile(self, conan_ref, conan_file):
        # Once the node is build, execute package info, so it has access to the
        # package folder and artifacts
        with conanfile_exception_formatter(str(conan_file), "package_info"):
            conan_file.package_info()

