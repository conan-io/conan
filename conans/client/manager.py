from conans.cli.output import ConanOutput
from conans.client.generators import write_generators
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_deploy, run_imports
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.model.conan_file import ConanFile
from conans.model.recipe_ref import RecipeReference


# FIXME: this is duplicated in the new API until all commands that use this function are migrated
#  this should be replaced by a call to APIV2.graph.load_graph + APIV2.install.install_binaries

def deps_install(app, ref_or_path, base_folder, profile_host, profile_build,
                 graph_lock, root_ref, build_modes=None, generators=None,
                 no_imports=False, create_reference=None,
                 is_build_require=False, require_overrides=None,
                 conanfile_path=None, test=None, source_folder=None, output_folder=None):
    """ Fetch and build all dependencies for the given reference
    @param app: The ConanApp instance with all collaborators
    @param ref_or_path: RecipeReference or path to user space conanfile
    @param build_modes: List of build_modes specified
    @param generators: List of generators from command line.
    @param no_imports: Install specified packages but avoid running imports
    """
    assert profile_host is not None
    assert profile_build is not None

    graph_manager, cache = app.graph_manager, app.cache

    out = ConanOutput()
    out.info("Configuration (profile_host):")
    out.info(profile_host.dumps())
    out.info("Configuration (profile_build):")
    out.info(profile_build.dumps())

    deps_graph = graph_manager.load_graph(ref_or_path, create_reference, profile_host, profile_build,
                                          graph_lock, root_ref, build_modes,
                                          is_build_require=is_build_require,
                                          require_overrides=require_overrides)

    deps_graph.report_graph_error()

    if graph_lock:
        graph_lock.update_lock(deps_graph)

    root_node = deps_graph.root
    conanfile = root_node.conanfile
    if root_node.recipe == RECIPE_VIRTUAL:
        out.highlight("Installing package: %s" % str(ref_or_path))
    else:
        conanfile.output.highlight("Installing package")
    print_graph(deps_graph)

    installer = BinaryInstaller(app)
    # TODO: Extract this from the GraphManager, reuse same object, check args earlier
    build_modes = BuildMode(build_modes)
    installer.install(deps_graph, build_modes)

    if hasattr(conanfile, "layout") and not test:
        conanfile.folders.set_base_source(source_folder or conanfile_path)
        conanfile.folders.set_base_imports(output_folder or conanfile_path)
        conanfile.folders.set_base_generators(output_folder or conanfile_path)
    else:
        conanfile.folders.set_base_imports(base_folder)
        conanfile.folders.set_base_generators(base_folder)

    # Write generators
    tmp = list(conanfile.generators)  # Add the command line specified generators
    generators = set(generators) if generators else set()
    tmp.extend([g for g in generators if g not in tmp])
    conanfile.generators = tmp
    write_generators(conanfile)

    if not no_imports:
        run_imports(conanfile)
    if type(conanfile).system_requirements != ConanFile.system_requirements:
        call_system_requirements(conanfile)

    if not create_reference and isinstance(ref_or_path, RecipeReference):
        # The conanfile loaded is a virtual one. The one w deploy is the first level one
        neighbours = deps_graph.root.neighbors()
        deploy_conanfile = neighbours[0].conanfile
        if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
            run_deploy(deploy_conanfile, output_folder or conanfile_path)

    return deps_graph
