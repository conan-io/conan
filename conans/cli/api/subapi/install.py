import os
import shutil

from conan import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.generators import write_generators

from conans.client.installer import BinaryInstaller, call_system_requirements


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
    def install_consumer(deps_graph, generators=None, source_folder=None, output_folder=None):
        """ Once a dependency graph has been installed, there are things to be done, like invoking
        generators for the root consumer.
        This is necessary for example for conanfile.txt/py, or for "conan install <ref> -g
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_generators(output_folder)
        conanfile.folders.set_base_build(output_folder)

        # Add cli -g generators
        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        write_generators(conanfile)

        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile)

    @staticmethod
    def deploy_consumer(deps_graph, generators=None, source_folder=None, output_folder=None):
        """ POC: Call the deployment of the consumer, at the moment doing a raw copy of everything
        and then hijacking the cpp_info/folders of the depedencies to point to the deployed
        location
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_generators(output_folder)

        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile)

        for r, d in conanfile.dependencies.items():
            new_folder = os.path.join(output_folder, d.ref.name)
            shutil.copytree(d.package_folder, new_folder)
            # FIXME: Ugly definition of package folder
            d._conanfile.cpp_info.deploy_base_folder(d.package_folder, new_folder)
            d._conanfile.folders.set_base_package(new_folder)

        # Add cli -g generators
        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        write_generators(conanfile)
