import os

from conans.client.cache.cache import ClientCache
from conans.client.generators import write_generators
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_deploy, run_imports
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.manifest_manager import ManifestManager
from conans.client.output import Color
from conans.client.source import complete_recipe_sources
from conans.client.tools import cross_building, get_cross_building_settings
from conans.client.userio import UserIO
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.paths import CONANINFO
from conans.util.files import normalize, save


class ConanManager(object):
    def __init__(self, cache, user_io, remote_manager,
                 recorder, graph_manager, hook_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(cache, ClientCache)
        self._cache = cache
        self._user_io = user_io
        self._remote_manager = remote_manager
        self._recorder = recorder
        self._graph_manager = graph_manager
        self._hook_manager = hook_manager

    def install(self, ref_or_path, install_folder, graph_info, remote_name=None, build_modes=None,
                update=False, manifest_folder=None, manifest_verify=False,
                manifest_interactive=False, generators=None, no_imports=False, create_reference=None,
                keep_build=False):
        """ Fetch and build all dependencies for the given reference
        @param ref_or_path: ConanFileReference or path to user space conanfile
        @param install_folder: where the output files will be saved
        @param remote_name: install only from that remote
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
        """

        if generators is not False:
            generators = set(generators) if generators else set()
            generators.add("txt")  # Add txt generator by default

        self._user_io.out.info("Configuration:")
        self._user_io.out.writeln(graph_info.profile.dumps())
        result = self._graph_manager.load_graph(ref_or_path, create_reference, graph_info,
                                                build_modes, False, update, remote_name,
                                                self._recorder)
        deps_graph, conanfile = result

        if conanfile.display_name == "virtual":
            self._user_io.out.highlight("Installing package: %s" % str(ref_or_path))
        else:
            conanfile.output.highlight("Installing package")
        print_graph(deps_graph, self._user_io.out)

        try:
            if cross_building(graph_info.profile.processed_settings):
                settings = get_cross_building_settings(graph_info.profile.processed_settings)
                message = "Cross-build from '%s:%s' to '%s:%s'" % settings
                self._user_io.out.writeln(message, Color.BRIGHT_MAGENTA)
        except ConanException:  # Setting os doesn't exist
            pass

        installer = BinaryInstaller(self._cache, self._user_io.out, self._remote_manager,
                                    recorder=self._recorder,
                                    hook_manager=self._hook_manager)
        installer.install(deps_graph, keep_build)

        if manifest_folder:
            manifest_manager = ManifestManager(manifest_folder, user_io=self._user_io,
                                               cache=self._cache)
            for node in deps_graph.nodes:
                if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                    continue
                complete_recipe_sources(self._remote_manager, self._cache, node.conanfile, node.ref)
            manifest_manager.check_graph(deps_graph,
                                         verify=manifest_verify,
                                         interactive=manifest_interactive)
            manifest_manager.print_log()

        if install_folder:
            # Write generators
            output = conanfile.output if conanfile.display_name != "virtual" else self._user_io.out
            if generators is not False:
                tmp = list(conanfile.generators)  # Add the command line specified generators
                tmp.extend([g for g in generators if g not in tmp])
                conanfile.generators = tmp
                write_generators(conanfile, install_folder, output)
            if not isinstance(ref_or_path, ConanFileReference):
                # Write conaninfo
                content = normalize(conanfile.info.dumps())
                save(os.path.join(install_folder, CONANINFO), content)
                output.info("Generated %s" % CONANINFO)
                graph_info.save(install_folder)
                output.info("Generated graphinfo")
            if not no_imports:
                run_imports(conanfile, install_folder)
            call_system_requirements(conanfile, conanfile.output)

            if not create_reference and isinstance(ref_or_path, ConanFileReference):
                # The conanfile loaded is a virtual one. The one w deploy is the first level one
                neighbours = deps_graph.root.neighbors()
                deploy_conanfile = neighbours[0].conanfile
                if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                    run_deploy(deploy_conanfile, install_folder)
