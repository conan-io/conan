import os

from conans.client import packager
from conans.client.client_cache import ClientCache
from conans.client.cmd.export import _execute_export
from conans.client.generators import write_generators
from conans.client.generators.text import TXTGenerator
from conans.client.importer import run_imports, run_deploy
from conans.client.installer import ConanInstaller, call_system_requirements
from conans.client.loader import ConanFileLoader
from conans.client.manifest_manager import ManifestManager
from conans.client.output import ScopedOutput, Color
from conans.client.profile_loader import read_conaninfo_profile
from conans.client.source import config_source_local, complete_recipe_sources
from conans.client.tools import cross_building, get_cross_building_settings
from conans.client.userio import UserIO
from conans.errors import NotFoundException, ConanException, conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO, CONANFILE_TXT, BUILD_INFO
from conans.util.files import save, rmdir, normalize, mkdir, load
from conans.util.log import logger
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.printer import print_graph
from conans.client.graph.graph import BINARY_BUILD


class ConanManager(object):
    """ Manage all the commands logic  The main entry point for all the client
    business logic
    """
    def __init__(self, client_cache, user_io, runner, remote_manager,
                 settings_preprocessor, recorder, registry):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._remote_manager = remote_manager
        self._settings_preprocessor = settings_preprocessor
        self._recorder = recorder
        self._registry = registry

    def _load_consumer_conanfile(self, conanfile_path, info_folder, output,
                                 deps_info_required=False):
        """loads a conanfile for local flow: source, imports, package, build
        """
        profile = read_conaninfo_profile(info_folder) or self._client_cache.default_profile
        loader = self.get_loader(profile, local=True)
        if conanfile_path.endswith(".py"):
            conanfile = loader.load_conan(conanfile_path, output, consumer=True, local=True)
        else:
            conanfile = loader.load_conan_txt(conanfile_path, output)

        _load_deps_info(info_folder, conanfile, required=deps_info_required)

        return conanfile

    def _load_install_conanfile(self, loader, reference_or_path):
        """loads a conanfile for installation: install, info
        """
        if isinstance(reference_or_path, ConanFileReference):
            conanfile = loader.load_virtual([reference_or_path])
        else:
            output = ScopedOutput("PROJECT", self._user_io.out)
            if reference_or_path.endswith(".py"):
                conanfile = loader.load_conan(reference_or_path, output, consumer=True)
            else:
                conanfile = loader.load_conan_txt(reference_or_path, output)
        return conanfile

    def get_loader(self, profile, local=False):
        """ When local=True it means that the state is being recovered from installed files
        conaninfo.txt, conanbuildinfo.txt, and only local methods as build() are being executed.
        Thus, it is necessary to restore settings from that info, as configure() is not called,
        being necessary to remove those settings that doesn't have a value
        """
        cache_settings = self._client_cache.settings.copy()
        cache_settings.values = profile.settings_values
        if local:
            cache_settings.remove_undefined()
        else:
            self._settings_preprocessor.preprocess(cache_settings)
        return ConanFileLoader(self._runner, cache_settings, profile)

    def export_pkg(self, reference, source_folder, build_folder, package_folder, install_folder, profile, force):

        conan_file_path = self._client_cache.conanfile(reference)
        if not os.path.exists(conan_file_path):
            raise ConanException("Package recipe '%s' does not exist" % str(reference))

        loader = self.get_loader(profile)
        conanfile = loader.load_virtual([reference], scope_options=True)
        graph_builder = self._get_graph_builder(loader, self._recorder)
        deps_graph = graph_builder.load_graph(conanfile, check_updates=False, update=False,
                                              build_mode=None)

        # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
        # which is the exported pkg
        nodes = deps_graph.root.neighbors()
        conanfile = nodes[0].conanfile
        if install_folder and existing_info_files(install_folder):
            _load_deps_info(install_folder, conanfile, required=True)
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
                                package_output)
        else:
            packager.create_package(conanfile, pkg_id, source_folder, build_folder,
                                    dest_package_folder, install_folder, package_output, local=True)

    @staticmethod
    def _inject_require(conanfile, inject_require):
        """ test_package functionality requires injecting the tested package as requirement
        before running the install
        """
        require = conanfile.requires.get(inject_require.name)
        if require:
            require.conan_reference = require.range_reference = inject_require
        else:
            conanfile.requires(str(inject_require))
        conanfile._user = inject_require.user
        conanfile._channel = inject_require.channel

    def _get_graph_builder(self, loader, action_recorder):
        graph_builder = GraphManager(self._user_io.out, loader,
                                     self._client_cache, self._registry, self._remote_manager,
                                     action_recorder, workspace=None)
        return graph_builder

    def _get_deps_graph(self, reference, profile, check_updates, update, build_mode,
                        remote_name):
        loader = self.get_loader(profile)
        conanfile = self._load_install_conanfile(loader, reference)
        graph_builder = self._get_graph_builder(loader, self._recorder)
        build_mode = BuildMode(build_mode, self._user_io.out)
        deps_graph = graph_builder.load_graph(conanfile, check_updates, update,
                                              build_mode=build_mode, remote_name=remote_name,
                                              profile_build_requires=profile.build_requires)
        return deps_graph, conanfile

    def info_build_order(self, reference, profile, build_order, remote_name, check_updates):
        deps_graph, _ = self._get_deps_graph(reference, profile, update=False,
                                             check_updates=check_updates, build_mode=["missing"],
                                             remote_name=remote_name)
        result = deps_graph.build_order(build_order)
        return result

    def info_nodes_to_build(self, reference, profile, build_mode, remote_name, check_updates):
        deps_graph, conanfile = self._get_deps_graph(reference, profile, update=False,
                                                     check_updates=check_updates, build_mode=build_mode,
                                                     remote_name=remote_name)
        ret = []
        for level in deps_graph.by_levels():
            for node in level:
                if node.binary == BINARY_BUILD:
                    if node.conan_ref not in ret:
                        ret.append(node.conan_ref)
        return ret, self._get_project_reference(reference, conanfile)

    def _get_project_reference(self, reference, conanfile):
        if isinstance(reference, ConanFileReference):
            project_reference = None
        else:
            project_reference = str(conanfile)

        return project_reference

    def info_get_graph(self, reference, profile, remote_name=None, check_updates=False, build_mode=None):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param remote: install only from that remote
        """
        deps_graph, conanfile = self._get_deps_graph(reference, profile,
                                                     update=False, check_updates=check_updates,
                                                     build_mode=build_mode, remote_name=remote_name)

        return deps_graph, self._get_project_reference(reference, conanfile)

    def install_workspace(self, profile, workspace, remote_name, build_modes, update):
        loader = self.get_loader(profile)
        references = [ConanFileReference(v, "root", "project", "develop") for v in workspace.root]
        conanfile = loader.load_virtual(references)

        graph_builder = GraphManager(self._user_io.out, loader,
                                     self._client_cache, self._registry, self._remote_manager,
                                     self._recorder, workspace=workspace)
        build_mode = BuildMode(build_modes, self._user_io.out)
        deps_graph = graph_builder.load_graph(conanfile, False, update, build_mode, remote_name,
                                              profile.build_requires)

        output = ScopedOutput(str("Workspace"), self._user_io.out)
        output.highlight("Installing...")
        print_graph(deps_graph, self._user_io.out)

        installer = ConanInstaller(self._client_cache, output, self._remote_manager,
                                   self._registry, recorder=self._recorder, workspace=workspace)
        installer.install(deps_graph, keep_build=False)

        build_mode.report_matches()
        workspace.generate()

    def install(self, reference, install_folder, profile, remote_name=None, build_modes=None,
                update=False, manifest_folder=None, manifest_verify=False,
                manifest_interactive=False, generators=None, no_imports=False, inject_require=None,
                install_reference=False, keep_build=False):
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

        loader = self.get_loader(profile)
        if not install_reference:
            if isinstance(reference, ConanFileReference):  # is a create
                loader.dev_reference = reference
            elif inject_require:
                loader.dev_reference = inject_require
        conanfile = self._load_install_conanfile(loader, reference)
        if inject_require:
            self._inject_require(conanfile, inject_require)

        graph_builder = self._get_graph_builder(loader, self._recorder)
        build_mode = BuildMode(build_modes, self._user_io.out)
        deps_graph = graph_builder.load_graph(conanfile, False, update, build_mode, remote_name,
                                              profile.build_requires)

        if not isinstance(reference, ConanFileReference):
            output = ScopedOutput(("%s (test package)" % str(inject_require)) if inject_require else "PROJECT",
                                  self._user_io.out)
            output.highlight("Installing %s" % reference)
        else:
            output = ScopedOutput(str(reference), self._user_io.out)
            output.highlight("Installing package")
        print_graph(deps_graph, self._user_io.out)
        build_mode.report_matches()

        try:
            if cross_building(loader._settings):
                b_os, b_arch, h_os, h_arch = get_cross_building_settings(loader._settings)
                message = "Cross-build from '%s:%s' to '%s:%s'" % (b_os, b_arch, h_os, h_arch)
                self._user_io.out.writeln(message, Color.BRIGHT_MAGENTA)
        except ConanException:  # Setting os doesn't exist
            pass

        installer = ConanInstaller(self._client_cache, output, self._remote_manager,
                                   self._registry, recorder=self._recorder, workspace=None)
        installer.install(deps_graph, keep_build)

        if manifest_folder:
            manifest_manager = ManifestManager(manifest_folder, user_io=self._user_io,
                                               client_cache=self._client_cache)
            for node in deps_graph.nodes:
                if not node.conan_ref:
                    continue
                conanfile = node.conanfile
                complete_recipe_sources(self._remote_manager, self._client_cache, self._registry,
                                        conanfile, node.conan_ref)
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

            if install_reference:
                # The conanfile loaded is really a virtual one. The one with the deploy is the first level one
                deploy_conanfile = deps_graph.inverse_levels()[1][0].conanfile
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
        conanfile = self._load_consumer_conanfile(conanfile_path, info_folder, output)
        conanfile_folder = os.path.dirname(conanfile_path)
        if conanfile_folder != source_folder:
            output.info("Executing exports to: %s" % source_folder)
            _execute_export(conanfile_path, conanfile, source_folder, source_folder, output)
        config_source_local(source_folder, conanfile, conanfile_folder, output)

    def imports(self, conan_file_path, dest_folder, info_folder):
        """
        :param conan_file_path: Abs path to a conanfile
        :param dest_folder:  Folder where to put the files
        :param info_folder: Folder containing the conaninfo/conanbuildinfo.txt files
        :return:
        """

        output = ScopedOutput("PROJECT", self._user_io.out)
        conanfile = self._load_consumer_conanfile(conan_file_path, info_folder,
                                                  output, deps_info_required=True)

        run_imports(conanfile, dest_folder, output)

    def local_package(self, package_folder, conanfile_path, build_folder, source_folder,
                      install_folder):
        if package_folder == build_folder:
            raise ConanException("Cannot 'conan package' to the build folder. "
                                 "--build-folder and package folder can't be the same")
        output = ScopedOutput("PROJECT", self._user_io.out)
        conanfile = self._load_consumer_conanfile(conanfile_path, install_folder, output,
                                                  deps_info_required=True)
        packager.create_package(conanfile, None, source_folder, build_folder, package_folder,
                                install_folder, output, local=True, copy_info=True)

    def build(self, conanfile_path, source_folder, build_folder, package_folder, install_folder,
              test=False, should_configure=True, should_build=True, should_install=True):
        """ Call to build() method saved on the conanfile.py
        param conanfile_path: path to a conanfile.py
        """
        logger.debug("Building in %s" % build_folder)
        logger.debug("Conanfile in %s" % conanfile_path)

        try:
            # Append env_vars to execution environment and clear when block code ends
            output = ScopedOutput(("%s (test package)" % test) if test else "Project",
                                  self._user_io.out)
            conan_file = self._load_consumer_conanfile(conanfile_path, install_folder, output,
                                                       deps_info_required=True)
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

        try:
            mkdir(build_folder)
            os.chdir(build_folder)
            conan_file.build_folder = build_folder
            conan_file.source_folder = source_folder
            conan_file.package_folder = package_folder
            conan_file.install_folder = install_folder
            with get_env_context_manager(conan_file):
                output.highlight("Running build()")
                with conanfile_exception_formatter(str(conan_file), "build"):
                    conan_file.build()
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


def _load_deps_info(current_path, conanfile, required):

    def get_forbidden_access_object(field_name):
        class InfoObjectNotDefined(object):
            def __getitem__(self, item):
                raise ConanException("self.%s not defined. If you need it for a "
                                     "local command run 'conan install'" % field_name)
            __getattr__ = __getitem__

        return InfoObjectNotDefined()

    if not current_path:
        return
    info_file_path = os.path.join(current_path, BUILD_INFO)
    try:
        deps_cpp_info, deps_user_info, deps_env_info = TXTGenerator.loads(load(info_file_path))
        conanfile.deps_cpp_info = deps_cpp_info
        conanfile.deps_user_info = deps_user_info
        conanfile.deps_env_info = deps_env_info
    except IOError:
        if required:
            raise ConanException("%s file not found in %s\nIt is required for this command\n"
                                 "You can generate it using 'conan install'"
                                 % (BUILD_INFO, current_path))
        conanfile.deps_cpp_info = get_forbidden_access_object("deps_cpp_info")
        conanfile.deps_user_info = get_forbidden_access_object("deps_user_info")
    except ConanException:
        raise ConanException("Parse error in '%s' file in %s" % (BUILD_INFO, current_path))


def existing_info_files(folder):
    return os.path.exists(os.path.join(folder, CONANINFO)) and  \
           os.path.exists(os.path.join(folder, BUILD_INFO))
