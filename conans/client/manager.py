import os

from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_deploy, run_imports
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.output import Color
from conans.client.generators import write_toolchain
from conans.client.tools import cross_building, get_cross_building_settings
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.ref import ConanFileReference
from conans.model.graph_lock import GraphLockFile, GraphLock


def deps_install(app, ref_or_path, install_folder, base_folder, profile_host, profile_build,
                 graph_lock, root_ref, remotes=None, build_modes=None, update=False, generators=None,
                 no_imports=False, create_reference=None, recorder=None, lockfile_node_id=None,
                 is_build_require=False, require_overrides=None):

    """ Fetch and build all dependencies for the given reference
    @param app: The ConanApp instance with all collaborators
    @param ref_or_path: ConanFileReference or path to user space conanfile
    @param install_folder: where the output files will be saved
    @param build_modes: List of build_modes specified
    @param update: Check for updated in the upstream remotes (and update)
    @param generators: List of generators from command line.
    @param no_imports: Install specified packages but avoid running imports
    """
    assert profile_host is not None
    assert profile_build is not None

    out, user_io, graph_manager, cache = app.out, app.user_io, app.graph_manager, app.cache

    out.info("Configuration (profile_host):")
    out.writeln(profile_host.dumps())
    out.info("Configuration (profile_build):")
    out.writeln(profile_build.dumps())

    deps_graph = graph_manager.load_graph(ref_or_path, create_reference, profile_host, profile_build,
                                          graph_lock, root_ref, build_modes, False, update, remotes,
                                          recorder, lockfile_node_id=lockfile_node_id,
                                          is_build_require=is_build_require,
                                          require_overrides=require_overrides)

    deps_graph.report_graph_error()
    graph_lock = graph_lock or GraphLock(deps_graph)  # After the graph is loaded it is defined
    root_node = deps_graph.root
    conanfile = root_node.conanfile
    if root_node.recipe == RECIPE_VIRTUAL:
        out.highlight("Installing package: %s" % str(ref_or_path))
    else:
        conanfile.output.highlight("Installing package")
    print_graph(deps_graph, out)

    try:
        if cross_building(conanfile):
            settings = get_cross_building_settings(conanfile)
            message = "Cross-build from '%s:%s' to '%s:%s'" % settings
            out.writeln(message, Color.BRIGHT_MAGENTA)
    except ConanException:  # Setting os doesn't exist
        pass

    installer = BinaryInstaller(app, recorder=recorder)
    # TODO: Extract this from the GraphManager, reuse same object, check args earlier
    build_modes = BuildMode(build_modes, out)
    installer.install(deps_graph, remotes, build_modes, update, profile_host, profile_build,
                      graph_lock)

    # graph_lock.complete_matching_prevs()

    conanfile.folders.set_base_install(install_folder)
    conanfile.folders.set_base_imports(install_folder)
    conanfile.folders.set_base_generators(base_folder)

    output = conanfile.output if root_node.recipe != RECIPE_VIRTUAL else out

    if install_folder:
        # Write generators
        tmp = list(conanfile.generators)  # Add the command line specified generators
        generators = set(generators) if generators else set()
        tmp.extend([g for g in generators if g not in tmp])
        conanfile.generators = tmp
        app.generator_manager.write_generators(conanfile, install_folder,
                                               conanfile.generators_folder,
                                               output)
        write_toolchain(conanfile, conanfile.generators_folder, output)

        #if not isinstance(ref_or_path, ConanFileReference):
        #    graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
        #    graph_lock_file.save(os.path.join(install_folder, "conan.lock"))
        if not no_imports:
            run_imports(conanfile)
        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile, conanfile.output)

        if not create_reference and isinstance(ref_or_path, ConanFileReference):
            # The conanfile loaded is a virtual one. The one w deploy is the first level one
            neighbours = deps_graph.root.neighbors()
            deploy_conanfile = neighbours[0].conanfile
            if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                run_deploy(deploy_conanfile, install_folder)

    return deps_graph
