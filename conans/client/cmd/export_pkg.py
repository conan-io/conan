import os

from conan.cache.conan_reference import ConanReference
from conans.client import packager
from conans.client.conanfile.package import run_package_method
from conans.client.graph.graph import BINARY_SKIP
from conans.client.installer import add_env_conaninfo
from conans.errors import ConanException
from conans.model.ref import PackageReference


def export_pkg(app, recorder, ref, source_folder, build_folder, package_folder,
               profile_host, profile_build, graph_lock, root_ref, force, remotes):
    cache, output, hook_manager = app.cache, app.out, app.hook_manager
    graph_manager = app.graph_manager
    conan_file_path = cache.ref_layout(ref).conanfile()
    if not os.path.exists(conan_file_path):
        raise ConanException("Package recipe '%s' does not exist" % str(ref))

    # The graph has to be loaded with build_mode=[ref.name], so that node is not tried
    # to be downloaded from remotes
    # passing here the create_reference=ref argument is useful so the recipe is in "develop",
    # because the "package()" method is in develop=True already
    deps_graph = graph_manager.load_graph(ref, ref, profile_host, profile_build, graph_lock,
                                          root_ref, build_mode=[ref.name], check_updates=False,
                                          update=False, remotes=remotes, recorder=recorder,
                                          apply_build_requires=False)
    # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
    # which is the exported pkg
    nodes = deps_graph.root.neighbors()
    pkg_node = nodes[0]
    conanfile = pkg_node.conanfile

    def _init_conanfile_infos():
        node_order = [n for n in pkg_node.public_closure if n.binary != BINARY_SKIP]
        subtree_libnames = [node.ref.name for node in node_order]
        add_env_conaninfo(conanfile, subtree_libnames)

    _init_conanfile_infos()

    package_id = pkg_node.package_id
    output.info("Packaging to %s" % package_id)
    pref = PackageReference(ref, package_id)
    pkg_ids = cache.get_package_ids(ref)
    existing_id = [pkg_id for pkg_id in pkg_ids if package_id in pkg_id]
    if existing_id:
        raise ConanException("Package already exists. Please use --force, -f to overwrite it")

    layout = cache.pkg_layout(pref)
    layout.package_remove()

    dest_package_folder = layout.package()
    conanfile.develop = True

    conanfile.folders.set_base_build(build_folder)
    conanfile.folders.set_base_source(source_folder)
    conanfile.folders.set_base_package(dest_package_folder)

    # TODO: cache2.0 check dirty management locks
    #with layout.set_dirty_context_manager(pref):
    if package_folder:
        prev = packager.export_pkg(conanfile, package_id, package_folder, hook_manager,
                                   conan_file_path, ref)
    else:
        prev = run_package_method(conanfile, package_id, hook_manager, conan_file_path, ref)

    pref = PackageReference(pref.ref, pref.id, prev)
    layout.assign_prev(ConanReference(pref))
    if pkg_node.graph_lock_node:
        # after the package has been created we need to update the node PREV
        pkg_node.prev = pref.revision
        pkg_node.graph_lock_node.prev = pref.revision
    recorder.package_exported(pref)
