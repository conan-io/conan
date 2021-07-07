from conans.client.output import ScopedOutput
from conans.client.source import retrieve_exports_sources
from conans.model.ref import ConanFileReference, PackageReference
from conans.errors import NotFoundException, RecipeNotFoundException, PackageNotFoundException
from multiprocessing.pool import ThreadPool


def download(app, ref, package_ids, remote, recipe, recorder, remotes):
    out, remote_manager, cache, loader = app.out, app.remote_manager, app.cache, app.loader
    hook_manager = app.hook_manager
    assert(isinstance(ref, ConanFileReference))
    output = ScopedOutput(str(ref), out)

    hook_manager.execute("pre_download", reference=ref, remote=remote)

    try:
        if not ref.revision:
            ref = remote_manager.get_latest_recipe_revision(ref, remote)
    except NotFoundException:
        raise RecipeNotFoundException(ref)
    else:
        ref_in_cache = cache.get_recipe_revisions(ref)
        ref = remote_manager.get_recipe(ref, remote) if len(ref_in_cache) == 0 else ref_in_cache[0]

    layout = cache.ref_layout(ref)
    conan_file_path = layout.conanfile()
    conanfile = loader.load_basic(conan_file_path)

    # Download the sources too, don't be lazy
    retrieve_exports_sources(remote_manager, cache, layout, conanfile, ref, remotes)

    if not recipe:  # Not only the recipe
        if not package_ids:  # User didn't specify a specific package binary
            output.info("Getting the complete package list from '%s'..." % ref.full_str())
            packages_props = remote_manager.search_packages(remote, ref, None)
            package_ids = list(packages_props.keys())
            if not package_ids:
                output.warn("No remote binary packages found in remote")

        parallel = cache.config.parallel_download
        _download_binaries(conanfile, ref, package_ids, cache, remote_manager,
                           remote, output, recorder, parallel)
    hook_manager.execute("post_download", conanfile_path=conan_file_path, reference=ref,
                         remote=remote)


def _download_binaries(conanfile, ref, package_ids, cache, remote_manager, remote, output,
                       recorder, parallel):

    def _download(package_id):
        pref = PackageReference(ref, package_id)
        try:
            if not pref.revision:
                pref = remote_manager.get_latest_package_revision(pref, remote)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        else:
            check_pref_cache = cache.get_package_revisions(pref)
            skip_download = (len(check_pref_cache) > 0)

        if output and not output.is_terminal:
            message = f"Downloading {str(pref)}" if not skip_download \
                else f"Skip {pref.full_str()} download, already in cache"
            output.info(message)

        if not skip_download:
            remote_manager.get_package(conanfile, pref, remote, output, recorder)

    if parallel is not None:
        output.info("Downloading binary packages in %s parallel threads" % parallel)
        thread_pool = ThreadPool(parallel)
        thread_pool.map(_download, [package_id for package_id in package_ids])
        thread_pool.close()
        thread_pool.join()
    else:
        for package_id in package_ids:
            _download(package_id)
