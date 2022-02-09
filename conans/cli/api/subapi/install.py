import os

from conan import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.generators import write_generators

from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.loader import load_python_file
from conans.errors import ConanException


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
    def install_consumer(self, deps_graph, generators=None, source_folder=None, output_folder=None,
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

        _do_deploys(self.conan_api, conanfile, deploy, output_folder)

        # Add cli -g generators
        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        write_generators(conanfile)

        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile)


def _do_deploys(conan_api, conanfile, deploy, output_folder):
    # Handle the deploys
    cwd = os.getcwd()
    for d in deploy or []:
        # First, find the file containing the deployer, could be local or in the cache
        if d.startswith("conan"):  # built-in!
            deployer = {"conan_full_deploy": conan_full_deploy}[d]
        else:
            if not d.endswith(".py"):
                d += ".py"  # Deployers must be python files
            if not os.path.isabs(d):
                full_path = os.path.normpath(os.path.join(cwd, d))  # Try first local path
                if not os.path.isfile(full_path):  # Then try in the cache
                    full_path = os.path.join(conan_api.cache_folder, "extensions", "deploy", d)
                    if not os.path.isfile(full_path):
                        raise ConanException(f"Cannot find deployer '{d}'")
            else:
                full_path = d
                if not os.path.isfile(full_path):
                    raise ConanException(f"Cannot find deployer '{d}'")

            mod, _ = load_python_file(full_path)
            deployer = mod.deploy

        deployer(conanfile, output_folder)


def conan_full_deploy(conanfile, output_folder):
    """
    Deploys to output_folder + host/dep/0.1/Release/x86_64 subfolder
    """
    # TODO: This deployer needs to be put somewhere else
    import os
    import shutil

    conanfile.output.info(f"Conan built-in full deployer to {output_folder}")
    for r, d in conanfile.dependencies.items():
        folder_name = os.path.join(d.context, d.ref.name, str(d.ref.version))
        build_type = str(d.info.settings.build_type)
        arch = str(d.info.settings.arch)
        if build_type:
            folder_name = os.path.join(folder_name, build_type)
        if arch:
            folder_name = os.path.join(folder_name, arch)
        new_folder = os.path.join(output_folder, folder_name)
        shutil.copytree(d.package_folder, new_folder)
        d.set_deploy_folder(new_folder)
