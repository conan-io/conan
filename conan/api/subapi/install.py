import os

from conan.internal.api.install.generators import write_generators
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanBasicApp
from conan.internal.deploy import do_deploys

from conans.client.graph.install_graph import InstallGraph
from conans.client.hook_manager import HookManager
from conans.client.installer import BinaryInstaller
from conan.errors import ConanInvalidConfiguration


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def install_binaries(self, deps_graph, remotes=None):
        """ Install binaries for dependency graph
        :param deps_graph: Dependency graph to intall packages for
        :param remotes:
        """
        app = ConanBasicApp(self.conan_api)
        installer = BinaryInstaller(app, self.conan_api.config.global_conf, app.editable_packages)
        install_graph = InstallGraph(deps_graph)
        install_graph.raise_errors()
        install_order = install_graph.install_order()
        installer.install_system_requires(deps_graph, install_order=install_order)
        installer.install(deps_graph, remotes, install_order=install_order)

    def install_system_requires(self, graph, only_info=False):
        """ Install binaries for dependency graph
        :param only_info: Only allow reporting and checking, but never install
        :param graph: Dependency graph to intall packages for
        """
        app = ConanBasicApp(self.conan_api)
        installer = BinaryInstaller(app, self.conan_api.config.global_conf, app.editable_packages)
        installer.install_system_requires(graph, only_info)

    def install_sources(self, graph, remotes):
        """ Install sources for dependency graph of packages to BUILD or packages that match
        tools.build:download_source conf
        :param remotes:
        :param graph: Dependency graph to install packages for
        """
        app = ConanBasicApp(self.conan_api)
        installer = BinaryInstaller(app, self.conan_api.config.global_conf, app.editable_packages)
        installer.install_sources(graph, remotes)

    # TODO: Look for a better name
    def install_consumer(self, deps_graph, generators=None, source_folder=None, output_folder=None,
                         deploy=False, deploy_package=None, deploy_folder=None, envs_generation=None):
        """ Once a dependency graph has been installed, there are things to be done, like invoking
        generators for the root consumer.
        This is necessary for example for conanfile.txt/py, or for "conan install <ref> -g
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        if conanfile.info is not None and conanfile.info.invalid:
            binary, reason = "Invalid", conanfile.info.invalid
            msg = "{}: Invalid ID: {}: {}".format(conanfile, binary, reason)
            raise ConanInvalidConfiguration(msg)

        if conanfile.info is not None and conanfile.info.cant_build and root_node.should_build:
            binary, reason = "Cannot build for this configuration", conanfile.info.cant_build
            msg = "{}: {}: {}".format(conanfile, binary, reason)
            raise ConanInvalidConfiguration(msg)

        conanfile.folders.set_base_folders(source_folder, output_folder)

        # The previous .set_base_folders has already decided between the source_folder and output
        if deploy or deploy_package:
            # Issue related: https://github.com/conan-io/conan/issues/16543
            base_folder = os.path.abspath(deploy_folder) if deploy_folder \
                else conanfile.folders.base_build
            do_deploys(self.conan_api.home_folder, deps_graph, deploy, deploy_package, base_folder)

        final_generators = []
        # Don't use set for uniqueness because order matters
        for gen in conanfile.generators:
            if gen not in final_generators:
                final_generators.append(gen)
        for gen in (generators or []):
            if gen not in final_generators:
                final_generators.append(gen)
        conanfile.generators = final_generators
        hook_manager = HookManager(HomePaths(self.conan_api.home_folder).hooks_path)
        write_generators(conanfile, hook_manager, self.conan_api.home_folder,
                         envs_generation=envs_generation)

    def deploy(self, graph, deployer, deploy_package=None, deploy_folder=None):
        return do_deploys(self.conan_api.home_folder, graph, deployer, deploy_package=deploy_package,
                          deploy_folder=deploy_folder)
