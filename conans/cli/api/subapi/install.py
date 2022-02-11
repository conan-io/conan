import os

from conan import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.generators import write_generators
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.loader import load_python_file
from conans.errors import ConanException
from conans.util.files import rmdir


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

        _do_deploys(self.conan_api, deps_graph, deploy, output_folder)

        # Add cli -g generators
        conanfile.generators = list(set(conanfile.generators).union(generators or []))
        write_generators(conanfile)

        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile)


# TODO: Look for a better location for the deployers code
def _find_deployer(d, cache_deploy_folder):
    """ implements the logic of finding a deployer, with priority:
    - 1) absolute paths
    - 2) relative to cwd
    - 3) in the cache/extensions/deploy folder
    - 4) built-in
    """
    def _load(path):
        mod, _ = load_python_file(path)
        return mod.deploy

    if not d.endswith(".py"):
        d += ".py"  # Deployers must be python files
    if os.path.isabs(d):
        return _load(d)
    cwd = os.getcwd()
    local_path = os.path.normpath(os.path.join(cwd, d))
    if os.path.isfile(local_path):
        return _load(local_path)
    cache_path = os.path.join(cache_deploy_folder, d)
    if os.path.isfile(cache_path):
        return _load(cache_path)
    if d == "full_deploy.py":
        return full_deploy
    raise ConanException(f"Cannot find deployer '{d}'")


def _do_deploys(conan_api, graph, deploy, output_folder):
    # Handle the deploys
    cache_deploy_folder = os.path.join(conan_api.cache_folder, "extensions", "deploy")
    for d in deploy or []:
        deployer = _find_deployer(d, cache_deploy_folder)
        # IMPORTANT: Use always kwargs to not break if it changes in the future
        conanfile = graph.root.conanfile
        deployer(conanfile=conanfile, output_folder=output_folder)


def full_deploy(conanfile, output_folder):
    """
    Deploys to output_folder + host/dep/0.1/Release/x86_64 subfolder
    """
    # TODO: This deployer needs to be put somewhere else
    # TODO: Document that this will NOT work with editables
    import os
    import shutil

    conanfile.output.info(f"Conan built-in full deployer to {output_folder}")
    for dep in conanfile.dependencies.values():
        folder_name = os.path.join(dep.context, dep.ref.name, str(dep.ref.version))
        build_type = str(dep.info.settings.build_type)
        arch = str(dep.info.settings.arch)
        if build_type:
            folder_name = os.path.join(folder_name, build_type)
        if arch:
            folder_name = os.path.join(folder_name, arch)
        new_folder = os.path.join(output_folder, folder_name)
        if os.path.isdir(new_folder):
            rmdir(new_folder)
        shutil.copytree(dep.package_folder, new_folder)
        dep.set_deploy_folder(new_folder)
