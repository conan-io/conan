import os
import shutil

from conan import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.generators import write_generators
from conans.client.graph.build_mode import BuildMode
from conans.client.importer import run_imports, run_deploy
from conans.client.installer import BinaryInstaller, call_system_requirements


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_binaries(self, deps_graph, build_modes=None, remotes=None, update=False):
        """ Install binaries for dependency graph
        @param deps_graph: Dependency graph to intall packages for
        @param build_modes:
        @param remotes:
        @param update:
        """
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes(remotes, update=update)
        installer = BinaryInstaller(app)
        # TODO: Extract this from the GraphManager, reuse same object, check args earlier
        build_modes = BuildMode(build_modes)
        installer.install(deps_graph, build_modes)

    # TODO: Look for a better name
    @staticmethod
    def install_consumer(deps_graph, generators=None, no_imports=False, deploy=False,
                         source_folder=None, output_folder=None):
        """ Once a dependency graph has been installed, there are things to be done, like invoking
        generators for the root consumer, or calling imports()/deploy() to copy things to user space.
        This is necessary for example for conanfile.txt/py, or for "conan install <ref> -g
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_imports(output_folder)
        conanfile.folders.set_base_generators(output_folder)
        conanfile.folders.set_base_build(output_folder)

        # Add cli -g generators
        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        write_generators(conanfile)

        if not no_imports:
            run_imports(conanfile)
        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile)

        if deploy:
            # The conanfile loaded is a virtual one. The one w deploy is the first level one
            neighbours = deps_graph.root.neighbors()
            deploy_conanfile = neighbours[0].conanfile
            deploy_conanfile.folders.set_base_imports(output_folder)
            if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                run_deploy(deploy_conanfile, output_folder)

    @staticmethod
    def deploy_consumer(deps_graph, generators=None, source_folder=None, output_folder=None):
        """ Once a dependency graph has been installed, there are things to be done, like invoking
        generators for the root consumer, or calling imports()/deploy() to copy things to user space.
        This is necessary for example for conanfile.txt/py, or for "conan install <ref> -g
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_imports(output_folder)
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
