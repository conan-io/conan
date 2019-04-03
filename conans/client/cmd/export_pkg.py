import os

from conans.client import packager
from conans.client.graph.graph_manager import load_deps_info
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.util.files import rmdir
from conans.model.conan_file import get_env_context_manager


def export_pkg(cache, graph_manager, hook_manager, recorder, output,
               ref, source_folder, build_folder, package_folder, install_folder,
               graph_info, force):

    conan_file_path = cache.conanfile(ref)
    if not os.path.exists(conan_file_path):
        raise ConanException("Package recipe '%s' does not exist" % str(ref))

    # The graph has to be loaded with build_mode=[ref.name], so that node is not tried
    # to be downloaded from remotes
    deps_graph, _ = graph_manager.load_graph(ref, None, graph_info=graph_info, build_mode=[ref.name],
                                             check_updates=False, update=False,
                                             remote_name=None, recorder=recorder,
                                             apply_build_requires=False)
    # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
    # which is the exported pkg
    nodes = deps_graph.root.neighbors()
    conanfile = nodes[0].conanfile
    from conans.client.conan_api import existing_info_files
    if install_folder and existing_info_files(install_folder):
        load_deps_info(install_folder, conanfile, required=True)
    package_id = nodes[0].package_id
    output.info("Packaging to %s" % package_id)
    pref = PackageReference(ref, package_id)
    dest_package_folder = cache.package(pref, short_paths=conanfile.short_paths)

    if os.path.exists(dest_package_folder):
        if force:
            rmdir(dest_package_folder)
        else:
            raise ConanException("Package already exists. Please use --force, -f to "
                                 "overwrite it")

    recipe_hash = cache.package_layout(ref).recipe_manifest().summary_hash
    conanfile.info.recipe_hash = recipe_hash
    conanfile.develop = True
    if package_folder:
        packager.export_pkg(conanfile, package_id, package_folder, dest_package_folder,
                            hook_manager, conan_file_path, ref)
    else:
        with get_env_context_manager(conanfile):
            packager.create_package(conanfile, package_id, source_folder, build_folder,
                                    dest_package_folder, install_folder, hook_manager,
                                    conan_file_path, ref, local=True)

    readed_manifest = FileTreeManifest.load(dest_package_folder)
    pref = PackageReference(pref.ref, pref.id, readed_manifest.summary_hash)
    output.info("Package revision %s" % pref.revision)
    with cache.package_layout(ref).update_metadata() as metadata:
        metadata.packages[package_id].revision = pref.revision
        metadata.packages[package_id].recipe_revision = metadata.recipe.revision

    recorder.package_exported(pref)
