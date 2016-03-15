import os
from conans.paths import CONANINFO, BUILD_INFO
from conans.util.files import save, rmdir, path_exists
from conans.model.ref import PackageReference
from conans.util.log import logger
from conans.errors import ConanException
from conans.client.packager import create_package
import shutil
from conans.client.generators import write_generators, TXTGenerator
from conans.model.build_info import CppInfo
import fnmatch
from conans.client.output import Color, ScopedOutput


class ConanInstaller(object):
    """ main responsible of retrieving binary packages or building them from source
    locally in case they are not found in remotes
    """
    def __init__(self, paths, user_io, remote_proxy):
        self._paths = paths
        self._out = user_io.out
        self._remote_proxy = remote_proxy

    def install(self, deps_graph, build_mode=False):
        """ given a DepsGraph object, build necessary nodes or retrieve them
        """
        self._deps_graph = deps_graph  # necessary for _build_package
        nodes_by_level = self._process_buildinfo(deps_graph)
        skip_private_nodes = self._compute_private_nodes(deps_graph, build_mode)
        self._build(nodes_by_level, skip_private_nodes, build_mode)

    def _process_buildinfo(self, deps_graph):
        """ once we have a dependency graph of conans, we have to propagate the build
        flags exported from conans down the hierarchy. First step is to assign a new
        BoxInfo object to each conans. Done here because we need the current
        folder of the package, the place it will be located. Then, upstream conans
        passes their exported build flags and included directories to the downstream
        imports flags
        """
        # Assign export root folders
        for node in deps_graph.nodes:
            conan_ref, conan_file = node
            if conan_ref:
                package_id = conan_file.info.package_id()
                package_reference = PackageReference(conan_ref, package_id)
                package_folder = self._paths.package(package_reference)
                conan_file.cpp_info = CppInfo(package_folder)
                try:
                    conan_file.package_info()
                except Exception as e:
                    raise ConanException("Error in %s\n\tpackage_info()\n\t%s"
                                         % (conan_ref, str(e)))

        # order by levels and propagate exports as download imports
        nodes_by_level = deps_graph.propagate_buildinfo()
        return nodes_by_level

    def _compute_private_nodes(self, deps_graph, build_mode):
        """ computes a list of nodes that are not required to be built, as they are
        private requirements of already available shared libraries as binaries
        """
        private_closure = deps_graph.private_nodes()
        skippable_nodes = []
        for private_node, private_requirers in private_closure:
            for private_requirer in private_requirers:
                conan_ref, conan_file = private_requirer
                if conan_ref is None:
                    break
                package_id = conan_file.info.package_id()
                package_reference = PackageReference(conan_ref, package_id)
                force_build = self._force_build(conan_ref, build_mode)
                if not self._remote_proxy.get_package(package_reference, force_build):
                    break
            else:
                skippable_nodes.append(private_node)
        return skippable_nodes

    def _force_build(self, conan_ref, build_mode):
        if build_mode is False:  # "never" option, default
            return False

        if build_mode is True:  # Build missing (just if needed), not force
            return False

        # Patterns to match, if package matches pattern, build is forced
        force_build = any([fnmatch.fnmatch(str(conan_ref), pattern)
                           for pattern in build_mode])
        return force_build

    def _build(self, nodes_by_level, skip_private_nodes, build_mode):
        """ The build assumes an input of conans ordered by degree, first level
        should be indpendent from each other, the next-second level should have
        dependencies only to first level conans.
        param nodes_by_level: list of lists [[nodeA, nodeB], [nodeC], [nodeD, ...], ...]
        """
        # Now build each level, starting from the most independent one
        for level in nodes_by_level:
            for node in level:
                if node in skip_private_nodes:
                    continue
                conan_ref, conan_file = node
                # it is possible that the root conans
                # is not inside the storage but in a user folder, and thus its
                # treatment is different
                if not conan_ref:
                    continue
                logger.debug("Building node %s" % repr(conan_ref))
                self._build_node(conan_ref, conan_file, build_mode)

    def _build_node(self, conan_ref, conan_file, build_mode):
        # Compute conan_file package from local (already compiled) or from remote
        output = ScopedOutput(str(conan_ref), self._out)
        package_id = conan_file.info.package_id()
        package_reference = PackageReference(conan_ref, package_id)

        conan_ref = package_reference.conan
        package_folder = self._paths.package(package_reference)
        build_folder = self._paths.build(package_reference)
        src_folder = self._paths.source(conan_ref)
        export_folder = self._paths.export(conan_ref)

        # If already exists do not dirt the output, the common situation
        # is that package is already installed and OK. If don't, the proxy
        # will print some other message about it
        if not os.path.exists(package_folder):
            output.info("Installing package %s" % package_id)

        self._handle_system_requirements(conan_ref, package_reference, conan_file, output)

        force_build = self._force_build(conan_ref, build_mode)
        if self._remote_proxy.get_package(package_reference, force_build):
            return

        # Can we build? Only if we are forced or build_mode missing and package not exists
        build_allowed = force_build or build_mode is True

        if build_allowed:
            rmdir(build_folder)
            rmdir(package_folder)
            if force_build:
                output.warn('Forced build from source')

            self._build_package(export_folder, src_folder, build_folder, conan_file, output)

            # Creating ***info.txt files
            save(os.path.join(build_folder, CONANINFO), conan_file.info.dumps())
            output.info("Generated %s" % CONANINFO)
            save(os.path.join(build_folder, BUILD_INFO), TXTGenerator(conan_file.deps_cpp_info,
                                                                      conan_file.cpp_info).content)
            output.info("Generated %s" % BUILD_INFO)

            os.chdir(build_folder)
            create_package(conan_file, build_folder, package_folder, output)
        else:
            self._raise_package_not_found_error(conan_ref, conan_file)

    def _raise_package_not_found_error(self, conan_ref, conan_file):
        settings_text = ", ".join(conan_file.info.full_settings.dumps().splitlines())
        options_text = ", ".join(conan_file.info.full_options.dumps().splitlines())
        author_contact = " at '%s'" % conan_file.url if conan_file.url else ""

        raise ConanException('''Can't find a '%s' package for the specified options and settings

- Try to build from sources with "--build %s" parameter
- If it fails, you could try to contact the package author %s, report your configuration and try to collaborate to support it.

Package configuration:
- Settings: %s
- Options: %s''' % (conan_ref, conan_ref.name, author_contact, settings_text, options_text))

    def _handle_system_requirements(self, conan_ref, package_reference, conan_file, coutput):
        """ check first the system_reqs/system_requirements.txt existence, if not existing
        check package/sha1/
        """
        if "system_requirements" not in type(conan_file).__dict__:
            return

        system_reqs_path = self._paths.system_reqs(conan_ref)
        system_reqs_package_path = self._paths.system_reqs_package(package_reference)
        if os.path.exists(system_reqs_path) or os.path.exists(system_reqs_package_path):
            return

        try:
            output = conan_file.system_requirements()
        except Exception as e:
            coutput.error("while executing system_requirements(): %s" % str(e))
            raise ConanException("Error in system requirements")

        try:
            output = str(output or "")
        except:
            coutput.warn("System requirements didn't return a string")
            output = ""
        if getattr(conan_file, "global_system_requirements", None):
            save(system_reqs_path, output)
        else:
            save(system_reqs_package_path, output)

    def _config_source(self, export_folder, src_folder, conan_file, output):
        """ creates src folder and retrieve, calling source() from conanfile
        the necessary source code
        """
        if not os.path.exists(src_folder):
            output.info('Configuring sources in %s' % src_folder)
            shutil.copytree(export_folder, src_folder)
            os.chdir(src_folder)
            try:
                conan_file.source()
            except Exception as e:
                output.error("Error while executing source(): %s" % str(e))
                # in case source() fails (user error, typically), remove the src_folder
                # and raise to interrupt any other processes (build, package)
                os.chdir(export_folder)
                try:
                    rmdir(src_folder)
                except Exception as e_rm:
                    output.error("Unable to remove src folder %s\n%s" % (src_folder, str(e_rm)))
                    output.warn("**** Please delete it manually ****")
                raise ConanException("%s: %s" % (conan_file.name, str(e)))

    def _build_package(self, export_folder, src_folder, build_folder, conan_file, output):
        """ builds the package, creating the corresponding build folder if necessary
        and copying there the contents from the src folder. The code is duplicated
        in every build, as some configure processes actually change the source
        code
        """
        output.info('Building your package in %s' % build_folder)
        if not os.path.exists(build_folder):
            self._config_source(export_folder, src_folder, conan_file, output)
            output.info('Copying sources to build folder')
            shutil.copytree(src_folder, build_folder, symlinks=True)
        os.chdir(build_folder)
        conan_file._conanfile_directory = build_folder
        # Read generators from conanfile and generate the needed files
        write_generators(conan_file, build_folder, output)

        # Build step might need DLLs, binaries as protoc to generate source files
        # So execute imports() before build, storing the list of copied_files
        from conans.client.importer import FileImporter
        local_installer = FileImporter(self._deps_graph, self._paths, build_folder)
        conan_file.copy = local_installer
        conan_file.imports()
        copied_files = local_installer.execute()

        try:
            # This is necessary because it is different for user projects
            # than for packages
            conan_file._conanfile_directory = build_folder
            conan_file.build()
            self._out.writeln("")
            output.success("Package '%s' built" % os.path.basename(build_folder))
            output.info("Build folder %s" % build_folder)
        except Exception as e:
            os.chdir(src_folder)
            self._out.writeln("")
            output.error("Package '%s' build failed" % os.path.basename(build_folder))
            output.warn("Build folder %s" % build_folder)
            raise ConanException("%s: %s" % (conan_file.name, str(e)))
        finally:
            conan_file._conanfile_directory = export_folder
            # Now remove all files that were imported with imports()
            for f in copied_files:
                try:
                    os.remove(f)
                except Exception:
                    self._out.warn("Unable to remove imported file from build: %s" % f)
