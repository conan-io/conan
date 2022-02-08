from conan import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.generators import write_generators

from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.loader import load_python_file


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_binaries(self, deps_graph, remotes=None, update=False):
        """ Install binaries for dependency graph
        @param deps_graph: Dependency graph to intall packages for
        @param remotes:
        @param update:
        """
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes(remotes, update=update)
        installer = BinaryInstaller(app)
        # TODO: Extract this from the GraphManager, reuse same object, check args earlier
        installer.install(deps_graph)

    # TODO: Look for a better name
    @staticmethod
    def install_consumer(deps_graph, generators=None, source_folder=None, output_folder=None,
                         deploy=False):
        """ Once a dependency graph has been installed, there are things to be done, like invoking
        generators for the root consumer.
        This is necessary for example for conanfile.txt/py, or for "conan install <ref> -g
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_generators(output_folder)
        conanfile.folders.set_base_build(output_folder)

        if deploy:
            mod, _ = load_python_file(deploy)
            mod.deploy(conanfile, output_folder)

        # Add cli -g generators
        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        write_generators(conanfile)

        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile)
