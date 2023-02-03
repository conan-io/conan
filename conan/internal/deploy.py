import os

from conans.client.cache.cache import ClientCache
from conans.client.loader import load_python_file
from conans.errors import ConanException
from conans.util.files import rmdir


def _find_deployer(d, cache_deploy_folder):
    """ Implements the logic of finding a deployer, with priority:
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
    builtin_deploy = {"full_deploy.py": full_deploy,
                      "direct_deploy.py": direct_deploy}.get(d)
    if builtin_deploy is not None:
        return builtin_deploy
    raise ConanException(f"Cannot find deployer '{d}'")


def do_deploys(conan_api, graph, deploy, deploy_folder):
    # Handle the deploys
    cache = ClientCache(conan_api.cache_folder)
    for d in deploy or []:
        deployer = _find_deployer(d, cache.deployers_path)
        # IMPORTANT: Use always kwargs to not break if it changes in the future
        deployer(graph=graph, output_folder=deploy_folder)


def full_deploy(graph, output_folder):
    """
    Deploys to output_folder + host/dep/0.1/Release/x86_64 subfolder
    """
    # TODO: This deployer needs to be put somewhere else
    # TODO: Document that this will NOT work with editables
    import os
    import shutil

    conanfile = graph.root.conanfile
    conanfile.output.info(f"Conan built-in full deployer to {output_folder}")
    for dep in conanfile.dependencies.values():
        if dep.package_folder is None:
            continue
        folder_name = os.path.join(dep.context, dep.ref.name, str(dep.ref.version))
        build_type = dep.info.settings.get_safe("build_type")
        arch = dep.info.settings.get_safe("arch")
        if build_type:
            folder_name = os.path.join(folder_name, build_type)
        if arch:
            folder_name = os.path.join(folder_name, arch)
        new_folder = os.path.join(output_folder, folder_name)
        rmdir(new_folder)
        shutil.copytree(dep.package_folder, new_folder)
        dep.set_deploy_folder(new_folder)


def direct_deploy(graph, output_folder):
    """
    Deploys to output_folder a single package,
    """
    # TODO: This deployer needs to be put somewhere else
    # TODO: Document that this will NOT work with editables
    import os
    import shutil

    conanfile = graph.root.conanfile
    conanfile.output.info(f"Conan built-in pkg deployer to {output_folder}")
    # If the argument is --requires, the current conanfile is a virtual one with 1 single
    # dependency, the "reference" package. If the argument is a local path, then all direct
    # dependencies
    for dep in conanfile.dependencies.filter({"direct": True}).values():
        new_folder = os.path.join(output_folder, dep.ref.name)
        rmdir(new_folder)
        shutil.copytree(dep.package_folder, new_folder)
        dep.set_deploy_folder(new_folder)
