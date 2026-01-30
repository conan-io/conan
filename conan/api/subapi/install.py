import os
from typing import List

from conan.api.model import Remote
from conan.internal.api.install.generators import write_generators
from conan.internal.conan_app import ConanBasicApp
from conan.internal.deploy import do_deploys

from conan.internal.graph.install_graph import InstallGraph
from conan.internal.graph.installer import BinaryInstaller
from conan.errors import ConanInvalidConfiguration, ConanException


class InstallAPI:
    """ This is the InstallAPI.

    It provides methods to install binaries, sources,
    prepare the consumer folder with generators and deploy, etc., all of them
    based on an already resolved dependency graph.
    """

    def __init__(self, conan_api, helpers):
        self._conan_api = conan_api
        self._helpers = helpers

    def install_binaries(self, deps_graph, remotes: List[Remote] = None, return_install_error=False):
        """ Install binaries of a dependency graph.

        This is the equivalent to the ``conan install`` command, but working with an already
        resolved dependency graph, usually obtained from the corresponding ``GraphAPI`` methods.

        It will download the available packages from the given remotes,
        and then build the ones that were marked for build from source.

        System requirements will be installed as well, taking into account the
        ``tools.system.package_manager:mode`` conf to determine whether to install, check or skip them.

        :param deps_graph: Dependency graph to install packages for
        :param remotes: List of remotes to fetch packages from if necessary.
        :param return_install_error: If ``True``, do not raise an exception, but return it
        """
        app = ConanBasicApp(self._conan_api)
        installer = BinaryInstaller(app, self._helpers.global_conf, app.editable_packages,
                                    self._helpers.hook_manager)
        install_graph = InstallGraph(deps_graph)
        install_graph.raise_errors()
        install_order = install_graph.install_order()
        installer.install_system_requires(deps_graph, install_order=install_order)
        try:  # To be able to capture the output, report or save graph.json, then raise later
            installer.install(deps_graph, remotes, install_order=install_order)
        except ConanException as e:
            # If true, allows to return the exception, so progress can be reported like the
            # already built binaries to upload them
            if not return_install_error:
                raise
            return e

    def install_system_requires(self, graph, only_info=False):
        """ Install only the system requirements of a dependency graph.

        This is a subset of ``install_binaries`` which only deals with system requirements
        of an already resolved dependency graph,
        usually obtained from the corresponding ``GraphAPI`` methods.

        The ``tools.system.package_manager:mode`` conf will be taken into account to
        determine whether to install, check or skip system requirements.

        :param graph: Dependency graph to install system requirements for
        :param only_info: If ``True``, only reporting and checking of whether the system requirements are installed is performed.
        """
        app = ConanBasicApp(self._conan_api)
        installer = BinaryInstaller(app, self._helpers.global_conf, app.editable_packages,
                                    self._helpers.hook_manager)
        installer.install_system_requires(graph, only_info)

    def install_sources(self, graph, remotes: List[Remote]):
        """ Download sources in the given dependency graph.

        If the ``tools.build:download_source`` conf is ``True``, sources will be downloaded for
        every package in the graph, otherwise only the packages marked for build from source will
        have their sources downloaded.

        ``tools.build:download_source=True`` is useful when users want to inspect the source code
        of all dependencies, even the ones that are not built from source.

        After this method, the ``conanfile.source_folder`` on each node of the dependency graph
        for which the sources have been downloaded will be set to the folder where sources have been downloaded.

        :param remotes: List of remotes where the ``exports_sources`` of the packages might be located
        :param graph: Dependency graph to download sources from
        """
        app = ConanBasicApp(self._conan_api)
        installer = BinaryInstaller(app, self._helpers.global_conf, app.editable_packages,
                                    self._helpers.hook_manager)
        installer.install_sources(graph, remotes)

    def install_consumer(self, deps_graph, generators: List[str] = None, source_folder=None,
                         output_folder=None, deploy=False, deploy_package: List[str] = None,
                         deploy_folder=None, envs_generation=None):
        """ Prepare the folder of the root consumer of a dependency graph after installation
        of the dependencies.

        This ensures that the requested generators are created in the consumer folder,
        and also handles deployment if requested.

        :param deps_graph: Dependency graph whose root is the consumer we want to prepare
        :param generators: List of generators to be used in addition to the ones defined in the root conanfile, if any
        :param source_folder: Source folder of the consumer
        :param output_folder: Output folder of the consumer
        :param deploy: Deployer or list of deployers to be used for deployment
        :param deploy_package: Only deploy the packages matching these patterns (``None`` or empty for all)
        :param deploy_folder: Folder where to deploy, by default the build folder
        :param envs_generation: Anything other than ``None`` will activate the generation of virtual environment files for the root conanfile
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
            do_deploys(self._conan_api.home_folder, deps_graph, deploy, deploy_package, base_folder)

        final_generators = []
        # Don't use set for uniqueness because order matters
        for gen in conanfile.generators:
            if gen not in final_generators:
                final_generators.append(gen)
        for gen in (generators or []):
            if gen not in final_generators:
                final_generators.append(gen)
        conanfile.generators = final_generators
        hook_manager = self._helpers.hook_manager
        write_generators(conanfile, hook_manager, self._conan_api.home_folder,
                         envs_generation=envs_generation)

    def deploy(self, graph, deployer: List[str], deploy_package: List[str]=None,
               deploy_folder=None) -> None:
        """ Run the given deployer in the dependency graph.

        No checks are performed in the graph, it is assumed to be already resolved
        and in a valid state to be deployed from.

        :param graph: The dependency graph to deploy
        :param deployer: List of deployers to be used
        :param deploy_package: Only deploy the packages matching these patterns (``None`` or empty for all)
        :param deploy_folder: Folder where to deploy, by default the build folder
        """
        return do_deploys(self._conan_api.home_folder, graph, deployer,
                          deploy_package=deploy_package, deploy_folder=deploy_folder)
