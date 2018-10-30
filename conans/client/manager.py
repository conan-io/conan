import os

from conans.client.client_cache import ClientCache
from conans.client.generators import write_generators
from conans.client.importer import run_imports, run_deploy
from conans.client.installer import ConanInstaller, call_system_requirements
from conans.client.manifest_manager import ManifestManager
from conans.client.output import ScopedOutput, Color
from conans.client.source import complete_recipe_sources
from conans.client.tools import cross_building, get_cross_building_settings
from conans.client.userio import UserIO
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.paths import CONANINFO
from conans.util.files import save, normalize

from conans.client.graph.printer import print_graph


class ConanManager(object):
    def __init__(self, client_cache, user_io, remote_manager,
                 recorder, registry, graph_manager, hook_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._remote_manager = remote_manager
        self._recorder = recorder
        self._registry = registry
        self._graph_manager = graph_manager
        self._hook_manager = hook_manager

    def install_workspace(self, profile, workspace, remote_name, build_modes, update):
        references = [ConanFileReference(v, "root", "project", "develop") for v in workspace.root]
        deps_graph, _, _ = self._graph_manager.load_graph(references, None, profile, build_modes,
                                                          False, update, remote_name, self._recorder,
                                                          workspace)

        output = ScopedOutput(str("Workspace"), self._user_io.out)
        output.highlight("Installing...")
        print_graph(deps_graph, self._user_io.out)

        installer = ConanInstaller(self._client_cache, output, self._remote_manager,
                                   self._registry, recorder=self._recorder, workspace=workspace,
                                   hook_manager=self._hook_manager)
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
                                                build_modes, False, update, remote_name,
                                                self._recorder, None)
        deps_graph, conanfile, cache_settings = result

        if not isinstance(reference, ConanFileReference):
            output = ScopedOutput(("%s (test package)" % str(create_reference))
                                  if create_reference else "PROJECT",
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
                                   hook_manager=self._hook_manager)
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
                # The conanfile loaded is a virtual one. The one w deploy is the first level one
                neighbours = deps_graph.root.neighbors()
                deploy_conanfile = neighbours[0].conanfile
                if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                    run_deploy(deploy_conanfile, install_folder, output)
