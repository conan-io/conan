import os

from conans.client.output import ScopedOutput
from conans.client import packager
from conans.errors import ConanException

from conans.util.files import rmdir
from conans.model.ref import PackageReference
from conans.client.graph.graph_manager import load_deps_info


def export_pkg(client_cache, graph_manager, hook_manager, recorder, output,
               reference, source_folder, build_folder, package_folder, install_folder,
               profile, force):

    conan_file_path = client_cache.conanfile(reference)
    if not os.path.exists(conan_file_path):
        raise ConanException("Package recipe '%s' does not exist" % str(reference))

    deps_graph = graph_manager.load_simple_graph(reference, profile, recorder)

    # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
    # which is the exported pkg
    nodes = deps_graph.root.neighbors()
    conanfile = nodes[0].conanfile
    from conans.client.conan_api import existing_info_files
    if install_folder and existing_info_files(install_folder):
        load_deps_info(install_folder, conanfile, required=True)
    pkg_id = conanfile.info.package_id()
    output.info("Packaging to %s" % pkg_id)
    pkg_reference = PackageReference(reference, pkg_id)
    dest_package_folder = client_cache.package(pkg_reference, short_paths=conanfile.short_paths)

    if os.path.exists(dest_package_folder):
        if force:
            rmdir(dest_package_folder)
        else:
            raise ConanException("Package already exists. Please use --force, -f to "
                                 "overwrite it")

    recipe_hash = client_cache.load_manifest(reference).summary_hash
    conanfile.info.recipe_hash = recipe_hash
    conanfile.develop = True
    package_output = ScopedOutput(str(reference), output)
    if package_folder:
        packager.export_pkg(conanfile, pkg_id, package_folder, dest_package_folder, package_output,
                            hook_manager, conan_file_path, reference)
    else:
        packager.create_package(conanfile, pkg_id, source_folder, build_folder, dest_package_folder,
                                install_folder, package_output, hook_manager, conan_file_path,
                                reference, local=True)
    recorder.package_exported(pkg_reference)
