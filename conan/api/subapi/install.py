from conan.api.subapi import api_method
from conan.internal.conan_app import ConanApp
from conan.internal.deploy import do_deploys
from conans.client.generators import write_generators
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.errors import ConanInvalidConfiguration
from conans.util.files import mkdir


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_binaries(self, deps_graph, remotes=None, update=False):
        """ Install binaries for dependency graph
        :param deps_graph: Dependency graph to intall packages for
        :param remotes:
        :param update:
        """
        app = ConanApp(self.conan_api.cache_folder)
        installer = BinaryInstaller(app)
        # TODO: Extract this from the GraphManager, reuse same object, check args earlier
        installer.install(deps_graph, remotes)

    # TODO: Look for a better name
    def install_consumer(self, deps_graph, generators=None, source_folder=None, output_folder=None,
                         deploy=False):
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

        if root_node.cant_build and root_node.should_build:
            binary, reason = "Cannot build for this configuration", root_node.cant_build
            msg = "{}: {}: {}".format(conanfile, binary, reason)
            raise ConanInvalidConfiguration(msg)

        conanfile.folders.set_base_folders(source_folder, output_folder)

        # The previous .set_base_folders has already decided between the source_folder and output
        if deploy:
            base_folder = conanfile.folders.base_build
            mkdir(base_folder)
            do_deploys(self.conan_api, deps_graph, deploy, base_folder)

        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        app = ConanApp(self.conan_api.cache_folder)
        write_generators(conanfile, app.hook_manager)
        call_system_requirements(conanfile)
