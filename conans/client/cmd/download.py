from conans.cli.output import ScopedOutput, ConanOutput
from conans.client.source import retrieve_exports_sources
from conans.model.package_ref import PkgReference
from conans.errors import NotFoundException, RecipeNotFoundException, PackageNotFoundException, \
    ConanException
from multiprocessing.pool import ThreadPool

from conans.model.recipe_ref import RecipeReference


def download(app, ref, package_ids, recipe):
    remote_manager, cache, loader = app.remote_manager, app.cache, app.loader
    hook_manager = app.hook_manager
    assert(isinstance(ref, RecipeReference))
    scoped_output = ScopedOutput(str(ref), ConanOutput())
    remote = app.selected_remote
    if not remote:
        # FIXME: Probably this shouldn't be done, the "default" remote concept when no remote is
        #        specify is confusing. Probably it should be: Or I specify one or Conan iterates
        try:
            remote = app.enabled_remotes[0]
        except IndexError:
            raise ConanException("No active remotes configured")

    hook_manager.execute("pre_download", reference=ref, remote=remote)
    try:
        if ref.revision is None:
            ref = remote_manager.get_latest_recipe_reference(ref, remote)
        else:  # to make sure it exists in the server, the get_recipe() is only for valid things
            ref = remote_manager.get_recipe_revision_reference(ref, remote)
        remote_manager.get_recipe(ref, remote)
    except NotFoundException:
        raise RecipeNotFoundException(ref)

    layout = cache.ref_layout(ref)
    conan_file_path = layout.conanfile()
    conanfile = loader.load_basic(conan_file_path, display=ref)

    # Download the sources too, don't be lazy
    retrieve_exports_sources(remote_manager, layout, conanfile, ref, app.enabled_remotes)

    if not recipe:  # Not only the recipe
        if not package_ids:  # User didn't specify a specific package binary
            scoped_output.info("Getting the complete package list from '%s'..." % ref.repr_notime())
            packages = remote_manager.search_packages(remote, ref)
            package_ids = [p.package_id for p in packages.keys()]
            if not package_ids:
                scoped_output.warning("No remote binary packages found in remote")

        parallel = cache.new_config.get("core.download:parallel", int)
        _download_binaries(conanfile, ref, package_ids, cache, remote_manager, remote,
                           scoped_output, parallel)
    hook_manager.execute("post_download", conanfile_path=conan_file_path, reference=ref,
                         remote=remote)


def _download_binaries(conanfile, ref, package_ids, cache, remote_manager, remote, scoped_output,
                       parallel):

    def _download(package_id):
        pref = PkgReference(ref, package_id)
        try:
            if not pref.revision:
                pref = remote_manager.get_latest_package_reference(pref, remote)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        else:
            skip_download = cache.exists_prev(pref)

        if scoped_output and not scoped_output.is_terminal:
            message = f"Downloading {str(pref)}" if not skip_download \
                else f"Skip {str(pref)} download, already in cache"
            scoped_output.info(message)

        if not pref.revision:
            pref = remote_manager.get_latest_package_reference(pref, remote)
        if not skip_download:
            remote_manager.get_package(conanfile, pref, remote)

    if parallel is not None:
        scoped_output.info("Downloading binary packages in %s parallel threads" % parallel)
        thread_pool = ThreadPool(parallel)
        thread_pool.map(_download, [package_id for package_id in package_ids])
        thread_pool.close()
        thread_pool.join()
    else:
        for package_id in package_ids:
            _download(package_id)
