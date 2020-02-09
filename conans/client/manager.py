import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import datetime

from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.cmd.download import download
from conans.client.generators import write_generators
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_deploy, run_imports
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.client.manifest_manager import ManifestManager
from conans.client.output import Color
from conans.client.source import complete_recipe_sources
from conans.client.tools import cross_building, get_cross_building_settings
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANINFO
from conans.util.files import normalize, save

def cache_artifact(executor, app, remotes, remote, ref, pending_refs, in_flight_refs):
    cache, loader = app.cache, app.loader
    def on_done(*_):
        for requires_ref in future_task.result():
            pending_refs.add(requires_ref)
        in_flight_refs.remove(ref)

    conan_file_ref = ConanFileReference.loads(ref)
    conan_file_path = cache.package_layout(conan_file_ref).conanfile()
    if os.path.exists(conan_file_path):
        conanfile = loader.load_basic(conan_file_path)
        for require in getattr(conanfile, "requires", []):
            pending_refs.add(require)
        in_flight_refs.remove(ref)
    else:
        future_task = executor.submit(download, app, conan_file_ref, None, remote, False, ActionRecorder(), remotes)
        future_task.add_done_callback(on_done)

def deps_install(app, ref_or_path, install_folder, graph_info, remotes=None, build_modes=None,
                 update=False, manifest_folder=None, manifest_verify=False,
                 manifest_interactive=False, generators=None, no_imports=False,
                 create_reference=None, keep_build=False, use_lock=False, recorder=None):
    """ Fetch and build all dependencies for the given reference
    :param app: The ConanApp instance with all collaborators
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
    now = datetime.datetime.now()
    out, user_io, graph_manager, cache, loader = app.out, app.user_io, app.graph_manager, app.cache, app.loader
    remote_manager, hook_manager = app.remote_manager, app.hook_manager
    if generators is not False:
        generators = set(generators) if generators else set()
        generators.add("txt")  # Add txt generator by default
    out.info("Configuration:")

    downloaded_refs = set()
    profile_host = cache.default_profile
    profile_host.process_settings(cache)
    conanfile = loader.load_conanfile_txt(ref_or_path, profile_host)
    remote = remotes.get("artifactory")

    tracked_refs = set()
    in_flight_refs = set()
    pending_refs = set([str(req.ref) for req in conanfile.requires.values()])

    with ThreadPoolExecutor(max_workers=5) as executor:
        while pending_refs or in_flight_refs:
            for ref in list(pending_refs):
                pending_refs.remove(ref)
                if ref not in tracked_refs:
                    in_flight_refs.add(ref)
                    tracked_refs.add(ref)
                    cache_artifact(executor, app, remotes, remote, ref, pending_refs, in_flight_refs)
            time.sleep(0.05)

    # with ThreadPoolExecutor(max_workers=20) as executor:
    #     async def download_artifact(ref):
    #         downloaded_refs.add(ref)
    #         future_task = executor.submit(download, app, ConanFileReference.loads(ref), None, remote, False, ActionRecorder(), remotes)
    #         new_requires = await to_aio_future(future_task)
    #         next_refs = list(set([ref_name for ref_name in new_requires if ref_name not in downloaded_refs]))
    #         next_batch = [download_artifact(ref_name) for ref_name in next_refs]
    #         if next_batch:
    #             await asyncio.wait(next_batch)

    #     loop = asyncio.get_event_loop()
    #     loop.run_until_complete(asyncio.wait([download_artifact(str(req.ref)) for req in conanfile.requires.values()]))


    # with ThreadPoolExecutor(max_workers=30) as executor:
    #     packages_to_pull = [str(req.ref) for req in conanfile.requires.values()]
    #     while packages_to_pull:
    #         all_args = [(app, ConanFileReference.loads(ref), None, remote, False, ActionRecorder(), remotes) for ref in packages_to_pull]
    #         generated_tasks = executor.map(lambda args: download(*args), all_args)
    #         for ref in packages_to_pull:
    #             downloaded_refs.add(ref)
    #         next_batch = []
    #         for downloaded_requires in generated_tasks:
    #             for ref_name in downloaded_requires:
    #                 if ref_name not in next_batch and ref_name not in downloaded_refs:
    #                     next_batch.append(ref_name)
    #         packages_to_pull = next_batch

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
        if cross_building(graph_info.profile_host.processed_settings):
            settings = get_cross_building_settings(graph_info.profile_host.processed_settings)
            message = "Cross-build from '%s:%s' to '%s:%s'" % settings
            out.writeln(message, Color.BRIGHT_MAGENTA)
    except ConanException:  # Setting os doesn't exist
        pass

    installer = BinaryInstaller(app, recorder=recorder)
    # TODO: Extract this from the GraphManager, reuse same object, check args earlier
    build_modes = BuildMode(build_modes, out)
    installer.install(deps_graph, remotes, build_modes, update, keep_build=keep_build,
                      graph_info=graph_info)
    # GraphLock always != None here (because of graph_manager.load_graph)
    graph_info.graph_lock.update_check_graph(deps_graph, out)

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
            write_generators(conanfile, install_folder, output)
        if not isinstance(ref_or_path, ConanFileReference) or use_lock:
            # Write conaninfo
            content = normalize(conanfile.info.dumps())
            save(os.path.join(install_folder, CONANINFO), content)
            output.info("Generated %s" % CONANINFO)
            graph_info.save(install_folder)
            output.info("Generated graphinfo")
        if not no_imports:
            run_imports(conanfile, install_folder)
        call_system_requirements(conanfile, conanfile.output)

        if not create_reference and isinstance(ref_or_path, ConanFileReference):
            # The conanfile loaded is a virtual one. The one w deploy is the first level one
            neighbours = deps_graph.root.neighbors()
            deploy_conanfile = neighbours[0].conanfile
            if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                run_deploy(deploy_conanfile, install_folder)

    print("total time = ", datetime.datetime.now() - now)
