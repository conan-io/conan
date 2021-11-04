import os

from conan.cache.conan_reference import ConanReference
from conans.cli.output import ConanOutput
from conans.client import packager
from conans.client.conanfile.package import run_package_method


from conans.client.graph.graph import BINARY_INVALID
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.model.package_ref import PkgReference


def export_pkg(app, ref, source_folder, build_folder, package_folder,
               profile_host, profile_build, graph_lock, root_ref, force,
               source_conanfile_path):
    cache, hook_manager = app.cache, app.hook_manager
    graph_manager = app.graph_manager
    conan_file_path = cache.ref_layout(ref).conanfile()
    if not os.path.exists(conan_file_path):
        raise ConanException("Package recipe '%s' does not exist" % str(ref))

    # The graph has to be loaded with build_mode=[ref.name], so that node is not tried
    # to be downloaded from remotes
    # passing here the create_reference=ref argument is useful so the recipe is in "develop",
    # because the "package()" method is in develop=True already

    deps_graph = graph_manager.load_graph(ref, ref, profile_host, profile_build, graph_lock,
                                          root_ref, build_mode=[ref.name])
    deps_graph.report_graph_error()
    # this is a bit tricky, but works. The root (virtual), has only 1 neighbor,
    # which is the exported pkg
    nodes = deps_graph.root.neighbors()
    pkg_node = nodes[0]
    if pkg_node.binary == BINARY_INVALID:
        binary, reason = pkg_node.conanfile.info.invalid
        msg = "{}: Invalid ID: {}: {}".format(ref, binary, reason)
        raise ConanInvalidConfiguration(msg)
    conanfile = pkg_node.conanfile

    package_id = pkg_node.package_id
    ConanOutput().info("Packaging to %s" % package_id)
    pref = PkgReference(ref, package_id)
    pkg_refs = cache.get_package_references(ref)

    existing_id = any(pref.package_id == package_id for pref in pkg_refs)
    if existing_id and not force:
        raise ConanException("Package already exists. Please use --force, -f to overwrite it")

    pkg_layout = cache.pkg_layout(pref) if pref.revision else cache.create_temp_pkg_layout(pref)
    pkg_layout.package_remove()

    dest_package_folder = pkg_layout.package()
    conanfile.develop = True
    if hasattr(conanfile, "layout"):
        conanfile_folder = os.path.dirname(source_conanfile_path)
        conanfile.folders.set_base_build(conanfile_folder)
        conanfile.folders.set_base_source(conanfile_folder)
        conanfile.folders.set_base_package(dest_package_folder)
        conanfile.folders.set_base_install(conanfile_folder)
        conanfile.folders.set_base_generators(conanfile_folder)
    else:
        conanfile.folders.set_base_build(build_folder)
        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_package(dest_package_folder)

    with pkg_layout.set_dirty_context_manager():
        if package_folder:
            # FIXME: To be removed in 2.0
            prev = packager.export_pkg(conanfile, package_id, package_folder, hook_manager,
                                       conan_file_path, ref)
        else:
            prev = run_package_method(conanfile, package_id, hook_manager, conan_file_path, ref)

    pref = PkgReference(pref.ref, pref.package_id, prev)
    pkg_layout.reference = ConanReference(pref)
    cache.assign_prev(pkg_layout)
    # Make sure folder is updated
    conanfile.folders.set_base_package(pkg_layout.package())
