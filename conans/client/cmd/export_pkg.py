import os

from conans.client import packager
from conans.client.conanfile.package import run_package_method
from conans.client.graph.graph import BINARY_SKIP, BINARY_INVALID
from conans.client.graph.graph_manager import load_deps_info
from conans.client.installer import add_env_conaninfo
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.model.ref import PackageReference


def export_pkg(app, recorder, full_ref, source_folder, build_folder, package_folder, install_folder,
               graph_info, force, remotes, source_conanfile_path):
    ref = full_ref.copy_clear_rev()
    cache, output, hook_manager = app.cache, app.out, app.hook_manager
    graph_manager = app.graph_manager
    conan_file_path = cache.package_layout(ref).conanfile()
    if not os.path.exists(conan_file_path):
        raise ConanException("Package recipe '%s' does not exist" % str(ref))

    # The graph has to be loaded with build_mode=[ref.name], so that node is not tried
    # to be downloaded from remotes
    # passing here the create_reference=ref argument is useful so the recipe is in "develop",
    # because the "package()" method is in develop=True already
    deps_graph = graph_manager.load_graph(ref, ref, graph_info=graph_info, build_mode=[ref.name],
                                          check_updates=False, update=False, remotes=remotes,
                                          recorder=recorder, apply_build_requires=False)
    # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
    # which is the exported pkg
    nodes = deps_graph.root.neighbors()
    pkg_node = nodes[0]
    if pkg_node.binary == BINARY_INVALID:
        msg = "{}: Invalid ID: {}".format(ref, pkg_node.conanfile.info.invalid)
        raise ConanInvalidConfiguration(msg)
    conanfile = pkg_node.conanfile

    def _init_conanfile_infos():
        node_order = [n for n in pkg_node.public_closure if n.binary != BINARY_SKIP]
        subtree_libnames = [node.ref.name for node in node_order]
        add_env_conaninfo(conanfile, subtree_libnames)

    _init_conanfile_infos()
    from conans.client.conan_api import existing_info_files
    if install_folder and existing_info_files(install_folder):
        load_deps_info(install_folder, conanfile, required=True)
    package_id = pkg_node.package_id
    output.info("Packaging to %s" % package_id)
    pref = PackageReference(ref, package_id)
    layout = cache.package_layout(ref, short_paths=conanfile.short_paths)

    if layout.package_id_exists(package_id) and not force:
        raise ConanException("Package already exists. Please use --force, -f to overwrite it")

    layout.package_remove(pref)

    dest_package_folder = layout.package(pref)
    recipe_hash = layout.recipe_manifest().summary_hash
    conanfile.info.recipe_hash = recipe_hash
    conanfile.develop = True
    if hasattr(conanfile, "layout"):
        conanfile_folder = os.path.dirname(source_conanfile_path)
        conanfile.folders.set_base_folders(conanfile_folder, output_folder=None)
        conanfile.folders.set_base_package(dest_package_folder)
    else:
        conanfile.folders.set_base_build(build_folder)
        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_package(dest_package_folder)
        conanfile.folders.set_base_install(install_folder)

    with layout.set_dirty_context_manager(pref):
        if package_folder:
            # FIXME: To be removed in 2.0
            prev = packager.export_pkg(conanfile, package_id, package_folder, hook_manager,
                                       conan_file_path, ref)
        else:
            prev = run_package_method(conanfile, package_id, hook_manager, conan_file_path, ref)

    packager.update_package_metadata(prev, layout, package_id, full_ref.revision)
    pref = PackageReference(pref.ref, pref.id, prev)
    if pkg_node.graph_lock_node:
        pkg_node.graph_lock_node.relax()
        pkg_node.graph_lock_node.unlock_prev()
        # after the package has been created we need to update the node PREV
        pkg_node.prev = pref.revision
        pkg_node.graph_lock_node.prev = pref.revision
    recorder.package_exported(pref)
