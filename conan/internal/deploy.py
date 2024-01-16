import os
import shutil

from conan.internal.cache.home_paths import HomePaths
from conan.api.output import ConanOutput
from conans.client.loader import load_python_file
from conans.errors import ConanException
from conans.model.recipe_ref import ref_matches
from conans.util.files import rmdir, mkdir


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
                      "direct_deploy.py": direct_deploy,
                      "runtime_deploy.py": runtime_deploy}.get(d)
    if builtin_deploy is not None:
        return builtin_deploy
    raise ConanException(f"Cannot find deployer '{d}'")


def do_deploys(conan_api, graph, deploy, deploy_package, deploy_folder):
    mkdir(deploy_folder)
    # handle the recipe deploy()
    if deploy_package:
        for node in graph.ordered_iterate():
            conanfile = node.conanfile
            if not conanfile.ref or not any(ref_matches(conanfile.ref, p, None)
                                            for p in deploy_package):
                continue
            if hasattr(conanfile, "deploy"):
                conanfile.output.info("Executing deploy()")
                conanfile.deploy_folder = deploy_folder
                conanfile.deploy()
    # Handle the deploys
    cache = HomePaths(conan_api.cache_folder)
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
    conanfile = graph.root.conanfile
    conanfile.output.info(f"Conan built-in full deployer to {output_folder}")
    for dep in conanfile.dependencies.values():
        if dep.package_folder is None:
            continue
        folder_name = os.path.join("full_deploy", dep.context, dep.ref.name, str(dep.ref.version))
        build_type = dep.info.settings.get_safe("build_type")
        arch = dep.info.settings.get_safe("arch")
        if build_type:
            folder_name = os.path.join(folder_name, build_type)
        if arch:
            folder_name = os.path.join(folder_name, arch)
        _deploy_single(dep, conanfile, output_folder, folder_name)


def runtime_deploy(graph, output_folder):
    """
    Deploy all the shared libraries and the executables of the dependencies in a flat directory.
    """
    conanfile = graph.root.conanfile
    conanfile.output.info(f"Deploying the runtime...")
    mkdir(output_folder)
    for _, dep in conanfile.dependencies.items():
        conanfile.output.verbose(f"Searching for shared libraries and executables in {dep.ref}...")
        if dep.package_folder is None:
            conanfile.output.verbose(f"{dep.ref} does not have any package folder")
            continue
        if not dep.cpp_info.bindirs and not dep.cpp_info.libdirs:
            conanfile.output.verbose(f"{dep.ref} does not have any bin or lib directory")
            continue

        for bindir in dep.cpp_info.bindirs:
            if not os.path.isdir(bindir):
                conanfile.output.warning(f"{bindir} does not exist")
                continue
            count = _flatten_directory(dep, conanfile, bindir, output_folder)
            conanfile.output.info(f"Copied {count} files from {dep.ref}, directory named {bindir}")

        for libdir in dep.cpp_info.libdirs:
            if not os.path.isdir(libdir):
                conanfile.output.warning(f"{libdir} does not exist")
                continue
            count = _flatten_directory(dep, conanfile, libdir, output_folder, [".dylib", ".so"])
            conanfile.output.info(f"Copied {count} files from {dep.ref}, directory named {libdir}")
    conanfile.output.info(f"Runtime deployed!")


def _flatten_directory(dep, conanfile, src_dir, output_dir, extension_filter=None):
    """
    Copy all the files from the source directory in a flat output directory.
    An optional string, named extension_filter, can be set to copy only the files with
    the listed extensions.
    """
    file_count = 0
    symlinks = conanfile.conf.get("tools.deployer:symlinks", check_type=bool, default=True)
    for src_dirpath, _, src_filenames in os.walk(src_dir, followlinks=symlinks):
        for src_filename in src_filenames:
            if extension_filter and not any(src_filename.endswith(ext) for ext in extension_filter):
                continue

            src_filepath = os.path.join(src_dirpath, src_filename)
            dest_filepath = os.path.join(output_dir, src_filename)
            if os.path.exists(dest_filepath):
                conanfile.output.warning(f"{src_filename} already exists and will be overwritten")
            try:
                file_count += 1
                shutil.copy2(src_filepath, dest_filepath, follow_symlinks=symlinks)
                conanfile.output.verbose(f"Copied {src_filename} into {output_dir}")
            except Exception as e:
                if "WinError 1314" in str(e):
                    ConanOutput().error("runtime_deploy: Symlinks in Windows require admin privileges "
                                        "or 'Developer mode = ON'", error_type="exception")
                raise ConanException(f"runtime_deploy: The copy of '{dep}' files failed: {e}.\nYou can "
                                     f"use 'tools.deployer:symlinks' conf to disable symlinks")
    return file_count


def _deploy_single(dep, conanfile, output_folder, folder_name):
    new_folder = os.path.join(output_folder, folder_name)
    rmdir(new_folder)
    symlinks = conanfile.conf.get("tools.deployer:symlinks", check_type=bool, default=True)
    try:
        shutil.copytree(dep.package_folder, new_folder, symlinks=symlinks)
    except Exception as e:
        if "WinError 1314" in str(e):
            ConanOutput().error("full_deploy: Symlinks in Windows require admin privileges "
                                "or 'Developer mode = ON'", error_type="exception")
        raise ConanException(f"full_deploy: The copy of '{dep}' files failed: {e}.\nYou can "
                             f"use 'tools.deployer:symlinks' conf to disable symlinks")
    dep.set_deploy_folder(new_folder)


def direct_deploy(graph, output_folder):
    """
    Deploys to output_folder a single package,
    """
    # TODO: This deployer needs to be put somewhere else
    # TODO: Document that this will NOT work with editables
    output_folder = os.path.join(output_folder, "direct_deploy")
    conanfile = graph.root.conanfile
    conanfile.output.info(f"Conan built-in pkg deployer to {output_folder}")
    # If the argument is --requires, the current conanfile is a virtual one with 1 single
    # dependency, the "reference" package. If the argument is a local path, then all direct
    # dependencies
    for dep in conanfile.dependencies.filter({"direct": True}).values():
        _deploy_single(dep, conanfile, output_folder, dep.ref.name)
