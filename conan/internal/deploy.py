import glob
import os
import shutil

from conan.internal.cache.home_paths import HomePaths
from conan.api.output import ConanOutput
from conans.client.loader import load_python_file
from conans.errors import ConanException, conanfile_exception_formatter
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
                      "merged_deploy.py": merged_deploy,
                      "shared_deploy.py": shared_deploy}.get(d)
    if builtin_deploy is not None:
        return builtin_deploy
    raise ConanException(f"Cannot find deployer '{d}'")


def do_deploys(conan_api, graph, deploy, deploy_package, deploy_folder):
    mkdir(deploy_folder)
    # handle the recipe deploy()
    if deploy_package:
        # Similar processing as BuildMode class
        excluded = [p[1:] for p in deploy_package if p[0] in ["!", "~"]]
        included = [p for p in deploy_package if p[0] not in ["!", "~"]]
        for node in graph.ordered_iterate():
            conanfile = node.conanfile
            if not conanfile.ref:  # virtual or conanfile.txt, can't have deployer
                continue
            consumer = conanfile._conan_is_consumer
            if any(conanfile.ref.matches(p, consumer) for p in excluded):
                continue
            if not any(conanfile.ref.matches(p, consumer) for p in included):
                continue
            if hasattr(conanfile, "deploy"):
                conanfile.output.info("Executing deploy()")
                conanfile.deploy_folder = deploy_folder
                with conanfile_exception_formatter(conanfile, "deploy"):
                    conanfile.deploy()
    # Handle the deploys
    cache = HomePaths(conan_api.cache_folder)
    for d in deploy or []:
        deployer = _find_deployer(d, cache.deployers_path)
        # IMPORTANT: Use always kwargs to not break if it changes in the future
        deployer(graph=graph, output_folder=deploy_folder)


def full_deploy(graph, output_folder):
    """
    Deploys all dependencies into
    <deploy-folder>/full_deploy/<host/build>/<package-name>/<version>/<build-type>/<arch>
    folder structure.
    """
    # TODO: This deployer needs to be put somewhere else
    # TODO: Document that this will NOT work with editables
    conanfile = graph.root.conanfile
    output = ConanOutput(scope="full_deploy")
    output.info(f"Deploying to {output_folder}")
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
        _deploy_package_folder(dep, conanfile, output_folder, folder_name, output)


def direct_deploy(graph, output_folder):
    """
    Deploy all direct dependencies with <deploy-folder>/direct_deploy/<package-name> folder structure.
    """
    # TODO: This deployer needs to be put somewhere else
    # TODO: Document that this will NOT work with editables
    output_folder = os.path.join(output_folder, "direct_deploy")
    conanfile = graph.root.conanfile
    output = ConanOutput(scope="full_deploy")
    output.info(f"Deploying to {output_folder}")
    # If the argument is --requires, the current conanfile is a virtual one with 1 single
    # dependency, the "reference" package. If the argument is a local path, then all direct
    # dependencies
    for dep in conanfile.dependencies.filter({"direct": True}).values():
        _deploy_package_folder(dep, conanfile, output_folder, dep.ref.name, output)


def merged_deploy(graph, output_folder):
    """
    Merge all host dependency package folders into a single <deploy-folder>/merged_deploy folder.
    License files are copied as <deploy-folder>/merged_deploy/licenses/<package-name>.
    All non-license files must be unique across packages.
    """
    conanfile = graph.root.conanfile
    output = ConanOutput(scope="merged_deploy")
    output_folder = os.path.join(output_folder, "merged_deploy")
    rmdir(output_folder)
    mkdir(output_folder)
    ignored = shutil.ignore_patterns("licenses", "conaninfo.txt", "conanmanifest.txt")
    for _, dep in conanfile.dependencies.host.items():
        if dep.package_folder is None:
            output.error(f"{dep.ref} does not have a package folder, skipping")
            continue
        _copytree(dep.package_folder,
                  output_folder,
                  conanfile, dep, output, dirs_exist_ok=True, ignore=ignored)
        _copytree(os.path.join(dep.package_folder, "licenses"),
                  os.path.join(output_folder, "licenses", dep.ref.name),
                  conanfile, dep, output, dirs_exist_ok=True)
        dep.set_deploy_folder(output_folder)
    conanfile.output.success(f"Deployed dependencies to: {output_folder}")


def shared_deploy(graph, output_folder):
    """
    Deploy all shared libraries from host dependencies into <deploy-folder>.
    """
    conanfile = graph.root.conanfile
    output = ConanOutput(scope="shared_deploy")
    output.info(f"Deploying runtime dependencies to folder: {output_folder}")
    mkdir(output_folder)
    keep_symlinks = conanfile.conf.get("tools.deployer:symlinks", check_type=bool, default=True)
    for _, dep in conanfile.dependencies.host.items():
        if dep.package_folder is None:
            output.warning(f"{dep.ref} does not have a package folder, skipping")
            continue

        cpp_info = dep.cpp_info.aggregated_components()
        copied_libs = set()

        for bindir in cpp_info.bindirs:
            if not os.path.isdir(bindir):
                continue
            for lib in cpp_info.libs:
                if _copy_pattern(f"{lib}.dll", bindir, output_folder, keep_symlinks):
                    copied_libs.add(lib)

        for libdir in cpp_info.libdirs:
            if not os.path.isdir(libdir):
                continue
            for lib in cpp_info.libs:
                if _copy_pattern(f"lib{lib}.so*", libdir, output_folder, keep_symlinks):
                    copied_libs.add(lib)
                if _copy_pattern(f"lib{lib}.dylib", libdir, output_folder, keep_symlinks):
                    copied_libs.add(lib)

        output.info(f"Copied {len(copied_libs)} shared libraries from {dep.ref}: " +
                    ", ".join(sorted(copied_libs)))
        not_found = copied_libs - set(cpp_info.libs)
        if not_found:
            output.error(f"Some {dep.ref} libraries were not found: " +
                         ", ".join(sorted(not_found)))
    conanfile.output.success(f"Shared libraries deployed to folder: {output_folder}")


def _deploy_package_folder(dep, conanfile, output_folder, folder_name, output):
    new_folder = os.path.join(output_folder, folder_name)
    rmdir(new_folder)
    _copytree(dep.package_folder, new_folder, conanfile, dep, output)
    dep.set_deploy_folder(new_folder)


def _copytree(src, dst, conanfile, dep, output, **kwargs):
    symlinks = conanfile.conf.get("tools.deployer:symlinks", check_type=bool, default=True)
    try:
        shutil.copytree(src, dst, symlinks=symlinks, **kwargs)
    except Exception as e:
        if "WinError 1314" in str(e):
            output.error("Symlinks on Windows require admin privileges or 'Developer mode = ON'",
                         error_type="exception")
        err = f"{output.scope}: Copying of '{dep}' files failed: {e}."
        if symlinks:
            err += "\nYou can use 'tools.deployer:symlinks' conf to disable symlinks"
        raise ConanException(err)


def _copy_pattern(pattern, src_dir, output_dir, keep_symlinks):
    """
    Copies all files matching the pattern from src_dir to output_dir.
    Existing files are overwritten.
    """
    file_count = 0
    output = ConanOutput(scope="deploy_shared")
    for src in glob.glob(os.path.join(src_dir, pattern)):
        dst = os.path.join(output_dir, os.path.basename(src))
        try:
            if os.path.lexists(dst):
                os.remove(dst)
            shutil.copy2(src, dst, follow_symlinks=not keep_symlinks)
            output.verbose(f"Copied {src}")
            file_count += 1
        except Exception as e:
            raise ConanException(f"{output.scope}: Copying of '{src}' to '{dst}' failed: {e}.")
    return file_count
