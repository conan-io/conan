from conan import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.generators import write_generators
from conans.client.graph.build_mode import BuildMode
from conans.client.importer import run_imports
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
    def install_consumer(deps_graph, install_folder, base_folder, conanfile_folder,
                         generators=None, reference=None, no_imports=False, create_reference=None,
                         test=None, source_folder=None, output_folder=None):
        """ Once a dependency graph has been installed, there are things to be done, like invoking
        generators for the root consumer, or calling imports()/deploy() to copy things to user space.
        This is necessary for example for conanfile.txt/py, or for "conan install <ref> -g
        """
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        if hasattr(conanfile, "layout") and not test:
            conanfile.folders.set_base_source(source_folder or conanfile_folder)
            conanfile.folders.set_base_install(output_folder or conanfile_folder)
            conanfile.folders.set_base_imports(output_folder or conanfile_folder)
            conanfile.folders.set_base_generators(output_folder or conanfile_folder)
        else:
            conanfile.folders.set_base_install(install_folder)
            conanfile.folders.set_base_imports(install_folder)
            conanfile.folders.set_base_generators(base_folder)

        if install_folder:
            # Add cli -g generators
            conanfile.generators = list(set(conanfile.generators).union(generators or []))
            write_generators(conanfile)

            if not no_imports:
                run_imports(conanfile)
            if type(conanfile).system_requirements != ConanFile.system_requirements:
                call_system_requirements(conanfile)
