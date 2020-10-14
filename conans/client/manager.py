import os

from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_deploy, run_imports
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.manifest_manager import ManifestManager
from conans.client.output import Color
from conans.client.source import complete_recipe_sources
from conans.client.toolchain.base import write_toolchain
from conans.client.tools import cross_building, get_cross_building_settings
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.ref import ConanFileReference
from conans.model.graph_lock import GraphLockFile
from conans.paths import CONANINFO
from conans.util.files import normalize, save


def deps_install(app, ref_or_path, install_folder, graph_info, remotes=None, build_modes=None,
                 update=False, manifest_folder=None, manifest_verify=False,
                 manifest_interactive=False, generators=None, no_imports=False,
                 create_reference=None, keep_build=False, recorder=None):
    """ Fetch and build all dependencies for the given reference
    @param app: The ConanApp instance with all collaborators
    @param ref_or_path: ConanFileReference or path to user space conanfile
    @param install_folder: where the output files will be saved
    @param build_modes: List of build_modes specified
    @param update: Check for updated in the upstream remotes (and update)
    @param manifest_folder: Folder to install the manifests
    @param manifest_verify: Verify dependencies manifests against stored ones
    @param manifest_interactive: Install deps manifests in folder for later verify, asking user
    for confirmation
    @param generators: List of generators from command line. If False, no generator will be
    written
    @param no_imports: Install specified packages but avoid running imports

    """
    out, user_io, graph_manager, cache = app.out, app.user_io, app.graph_manager, app.cache
    remote_manager, hook_manager = app.remote_manager, app.hook_manager
    if generators is not False:
        generators = set(generators) if generators else set()
        generators.add("txt")  # Add txt generator by default

    if graph_info.profile_build:
        out.info("Configuration (profile_host):")
        out.writeln(graph_info.profile_host.dumps())
        out.info("Configuration (profile_build):")
        out.writeln(graph_info.profile_build.dumps())
    else:
        out.info("Configuration:")
        out.writeln(graph_info.profile_host.dumps())

    deps_graph = graph_manager.load_graph(ref_or_path, create_reference, graph_info, build_modes,
                                          False, update, remotes, recorder)
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
    installer.install(deps_graph, remotes, build_modes, update, keep_build=keep_build,
                      graph_info=graph_info)

    graph_info.graph_lock.complete_matching_prevs()

    if manifest_folder:
        manifest_manager = ManifestManager(manifest_folder, user_io=user_io, cache=cache)
        for node in deps_graph.nodes:
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            complete_recipe_sources(remote_manager, cache, node.conanfile, node.ref,
                                    remotes)
        manifest_manager.check_graph(deps_graph, verify=manifest_verify,
                                     interactive=manifest_interactive)
        manifest_manager.print_log()

    if install_folder:
        conanfile.install_folder = install_folder
        # Write generators
        output = conanfile.output if root_node.recipe != RECIPE_VIRTUAL else out
        if generators is not False:
            tmp = list(conanfile.generators)  # Add the command line specified generators
            tmp.extend([g for g in generators if g not in tmp])
            conanfile.generators = tmp
            app.generator_manager.write_generators(conanfile, install_folder, output)
            write_toolchain(conanfile, install_folder, output)
        if not isinstance(ref_or_path, ConanFileReference):
            # Write conaninfo
            content = normalize(conanfile.info.dumps())
            save(os.path.join(install_folder, CONANINFO), content)
            output.info("Generated %s" % CONANINFO)
            graph_info.save(install_folder)
            output.info("Generated graphinfo")
            graph_lock_file = GraphLockFile(graph_info.profile_host, graph_info.profile_build,
                                            graph_info.graph_lock)
            graph_lock_file.save(os.path.join(install_folder, "conan.lock"))
        if not no_imports:
            run_imports(conanfile, install_folder)
        if type(conanfile).system_requirements != ConanFile.system_requirements:
            call_system_requirements(conanfile, conanfile.output)

        if not create_reference and isinstance(ref_or_path, ConanFileReference):
            # The conanfile loaded is a virtual one. The one w deploy is the first level one
            neighbours = deps_graph.root.neighbors()
            deploy_conanfile = neighbours[0].conanfile
            if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                run_deploy(deploy_conanfile, install_folder)
