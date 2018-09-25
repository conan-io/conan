import os

from conans.client import packager
from conans.client.client_cache import ClientCache
from conans.client.cmd.export import _execute_export
from conans.client.generators import write_generators
from conans.client.importer import run_imports, run_deploy
from conans.client.installer import ConanInstaller, call_system_requirements
from conans.client.manifest_manager import ManifestManager
from conans.client.output import ScopedOutput, Color
from conans.client.source import config_source_local, complete_recipe_sources
from conans.client.tools import cross_building, get_cross_building_settings
from conans.client.userio import UserIO
from conans.errors import NotFoundException, ConanException, conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO, CONANFILE_TXT, BUILD_INFO
from conans.util.files import save, rmdir, normalize, mkdir
from conans.util.log import logger
from conans.client.graph.graph_manager import load_deps_info
from conans.client.graph.printer import print_graph


class ConanManager(object):
    """ Manage all the commands logic  The main entry point for all the client
    business logic
    """
    def __init__(self, client_cache, user_io, runner, remote_manager,
                 recorder, registry, graph_manager, plugin_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._remote_manager = remote_manager
        self._recorder = recorder
        self._registry = registry
        self._graph_manager = graph_manager
        self._plugin_manager = plugin_manager

    def export_pkg(self, reference, source_folder, build_folder, package_folder, install_folder, profile, force):

        conan_file_path = self._client_cache.conanfile(reference)
        if not os.path.exists(conan_file_path):
            raise ConanException("Package recipe '%s' does not exist" % str(reference))

        deps_graph = self._graph_manager.load_simple_graph(reference, profile, self._recorder)

        # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
        # which is the exported pkg
        nodes = deps_graph.root.neighbors()
        conanfile = nodes[0].conanfile
        if install_folder and existing_info_files(install_folder):
            load_deps_info(install_folder, conanfile, required=True)
        pkg_id = conanfile.info.package_id()
        self._user_io.out.info("Packaging to %s" % pkg_id)
        pkg_reference = PackageReference(reference, pkg_id)
        dest_package_folder = self._client_cache.package(pkg_reference,
                                                         short_paths=conanfile.short_paths)

        if os.path.exists(dest_package_folder):
            if force:
                rmdir(dest_package_folder)
            else:
                raise ConanException("Package already exists. Please use --force, -f to "
                                     "overwrite it")

        recipe_hash = self._client_cache.load_manifest(reference).summary_hash
        conanfile.info.recipe_hash = recipe_hash
        conanfile.develop = True
        package_output = ScopedOutput(str(reference), self._user_io.out)
        if package_folder:
            packager.export_pkg(conanfile, pkg_id, package_folder, dest_package_folder,
                                package_output, self._plugin_manager, conan_file_path, reference)
        else:
            packager.create_package(conanfile, pkg_id, source_folder, build_folder,
                                    dest_package_folder, install_folder, package_output,
                                    self._plugin_manager, conan_file_path, reference, local=True)

    def install_workspace(self, profile, workspace, remote_name, build_modes, update):
        references = [ConanFileReference(v, "root", "project", "develop") for v in workspace.root]
        deps_graph, _, _ = self._graph_manager.load_graph(references, None, profile, build_modes,
                                                          False, update, remote_name, self._recorder, workspace)

        output = ScopedOutput(str("Workspace"), self._user_io.out)
        output.highlight("Installing...")
        print_graph(deps_graph, self._user_io.out)

        installer = ConanInstaller(self._client_cache, output, self._remote_manager,
                                   self._registry, recorder=self._recorder, workspace=workspace,
                                   plugin_manager=self._plugin_manager)
        installer.install(deps_graph, keep_build=False)
        workspace.generate()

    def install(self, reference, install_folder, profile, remote_name=None, build_modes=None,
                update=False, manifest_folder=None, manifest_verify=False,
                manifest_interactive=False, generators=None, no_imports=False, create_reference=None,
                keep_build=False):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param install_folder: where the output files will be saved
        @param remote: install only from that remote
        @param profile: Profile object with both the -s introduced options and profile read values
        @param build_modes: List of build_modes specified
        @param update: Check for updated in the upstream remotes (and update)
        @param manifest_folder: Folder to install the manifests
        @param manifest_verify: Verify dependencies manifests against stored ones
        @param manifest_interactive: Install deps manifests in folder for later verify, asking user
        for confirmation
        @param generators: List of generators from command line. If False, no generator will be
        written
        @param no_imports: Install specified packages but avoid running imports
        @param inject_require: Reference to add as a requirement to the conanfile
        """

        if generators is not False:
            generators = set(generators) if generators else set()
            generators.add("txt")  # Add txt generator by default

        self._user_io.out.info("Configuration:")
        self._user_io.out.writeln(profile.dumps())
        result = self._graph_manager.load_graph(reference, create_reference, profile,
                                                build_modes, False, update, remote_name, self._recorder,
                                                None)
        deps_graph, conanfile, cache_settings = result

        if not isinstance(reference, ConanFileReference):
            output = ScopedOutput(("%s (test package)" % str(create_reference)) if create_reference else "PROJECT",
                                  self._user_io.out)
            output.highlight("Installing %s" % reference)
        else:
            output = ScopedOutput(str(reference), self._user_io.out)
            output.highlight("Installing package")
        print_graph(deps_graph, self._user_io.out)

        try:
            if cross_building(cache_settings):
                b_os, b_arch, h_os, h_arch = get_cross_building_settings(cache_settings)
                message = "Cross-build from '%s:%s' to '%s:%s'" % (b_os, b_arch, h_os, h_arch)
                self._user_io.out.writeln(message, Color.BRIGHT_MAGENTA)
        except ConanException:  # Setting os doesn't exist
            pass

        installer = ConanInstaller(self._client_cache, output, self._remote_manager,
                                   self._registry, recorder=self._recorder, workspace=None,
                                   plugin_manager=self._plugin_manager)
        installer.install(deps_graph, keep_build)

        if manifest_folder:
            manifest_manager = ManifestManager(manifest_folder, user_io=self._user_io,
                                               client_cache=self._client_cache)
            for node in deps_graph.nodes:
                if not node.conan_ref:
                    continue
                complete_recipe_sources(self._remote_manager, self._client_cache, self._registry,
                                        node.conanfile, node.conan_ref)
            manifest_manager.check_graph(deps_graph,
                                         verify=manifest_verify,
                                         interactive=manifest_interactive)
            manifest_manager.print_log()

        if install_folder:
            # Write generators
            if generators is not False:
                tmp = list(conanfile.generators)  # Add the command line specified generators
                tmp.extend([g for g in generators if g not in tmp])
                conanfile.generators = tmp
                write_generators(conanfile, install_folder, output)
            if not isinstance(reference, ConanFileReference):
                # Write conaninfo
                content = normalize(conanfile.info.dumps())
                save(os.path.join(install_folder, CONANINFO), content)
                output.info("Generated %s" % CONANINFO)
            if not no_imports:
                run_imports(conanfile, install_folder, output)
            call_system_requirements(conanfile, output)

            if not create_reference and isinstance(reference, ConanFileReference):
                # The conanfile loaded is really a virtual one. The one with the deploy is the first level one
                neighbours = deps_graph.root.neighbors()
                deploy_conanfile = neighbours[0].conanfile
                if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                    run_deploy(deploy_conanfile, install_folder, output)

    def source(self, conanfile_path, source_folder, info_folder):
        """
        :param conanfile_path: Absolute path to a conanfile
        :param source_folder: Absolute path where to put the files
        :param info_folder: Absolute path where to read the info files
        :param package_folder: Absolute path to the package_folder, only to have the var present
        :return:
        """
        output = ScopedOutput("PROJECT", self._user_io.out)
        # only infos if exist
        conanfile = self._graph_manager.load_consumer_conanfile(conanfile_path, info_folder, output)
        conanfile_folder = os.path.dirname(conanfile_path)
        if conanfile_folder != source_folder:
            output.info("Executing exports to: %s" % source_folder)
            _execute_export(conanfile_path, conanfile, source_folder, source_folder, output)
        config_source_local(source_folder, conanfile, conanfile_folder, output, conanfile_path,
                            self._plugin_manager)

    def imports(self, conan_file_path, dest_folder, info_folder):
        """
        :param conan_file_path: Abs path to a conanfile
        :param dest_folder:  Folder where to put the files
        :param info_folder: Folder containing the conaninfo/conanbuildinfo.txt files
        :return:
        """

        output = ScopedOutput("PROJECT", self._user_io.out)
        conanfile = self._graph_manager.load_consumer_conanfile(conan_file_path, info_folder, output,
                                                                deps_info_required=True)
        run_imports(conanfile, dest_folder, output)

    def local_package(self, package_folder, conanfile_path, build_folder, source_folder,
                      install_folder):
        if package_folder == build_folder:
            raise ConanException("Cannot 'conan package' to the build folder. "
                                 "--build-folder and package folder can't be the same")
        output = ScopedOutput("PROJECT", self._user_io.out)
        conanfile = self._graph_manager.load_consumer_conanfile(conanfile_path, install_folder,
                                                                output, deps_info_required=True)
        packager.create_package(conanfile, None, source_folder, build_folder, package_folder,
                                install_folder, output, self._plugin_manager, conanfile_path, None,
                                local=True, copy_info=True)

    def build(self, conanfile_path, source_folder, build_folder, package_folder, install_folder,
              test=False, should_configure=True, should_build=True, should_install=True,
              should_test=True):
        """ Call to build() method saved on the conanfile.py
        param conanfile_path: path to a conanfile.py
        """
        logger.debug("Building in %s" % build_folder)
        logger.debug("Conanfile in %s" % conanfile_path)

        try:
            # Append env_vars to execution environment and clear when block code ends
            output = ScopedOutput(("%s (test package)" % test) if test else "Project",
                                  self._user_io.out)
            conan_file = self._graph_manager.load_consumer_conanfile(conanfile_path, install_folder,
                                                                     output, deps_info_required=True)
        except NotFoundException:
            # TODO: Auto generate conanfile from requirements file
            raise ConanException("'%s' file is needed for build.\n"
                                 "Create a '%s' and move manually the "
                                 "requirements and generators from '%s' file"
                                 % (CONANFILE, CONANFILE, CONANFILE_TXT))

        if test:
            try:
                conan_file.requires.add(test)
            except ConanException:
                pass

        conan_file.should_configure = should_configure
        conan_file.should_build = should_build
        conan_file.should_install = should_install
        conan_file.should_test = should_test

        try:
            mkdir(build_folder)
            os.chdir(build_folder)
            conan_file.build_folder = build_folder
            conan_file.source_folder = source_folder
            conan_file.package_folder = package_folder
            conan_file.install_folder = install_folder
            self._plugin_manager.execute("pre_build", conanfile=conan_file,
                                         conanfile_path=conanfile_path)
            with get_env_context_manager(conan_file):
                output.highlight("Running build()")
                with conanfile_exception_formatter(str(conan_file), "build"):
                    conan_file.build()
                self._plugin_manager.execute("post_build", conanfile=conan_file,
                                             conanfile_path=conanfile_path)
                if test:
                    output.highlight("Running test()")
                    with conanfile_exception_formatter(str(conan_file), "test"):
                        conan_file.test()
        except ConanException:
            raise  # Raise but not let to reach the Exception except (not print traceback)
        except Exception:
            import traceback
            trace = traceback.format_exc().split('\n')
            raise ConanException("Unable to build it successfully\n%s" % '\n'.join(trace[3:]))


def existing_info_files(folder):
    return os.path.exists(os.path.join(folder, CONANINFO)) and  \
           os.path.exists(os.path.join(folder, BUILD_INFO))
