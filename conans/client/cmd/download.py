from conans.client.output import ScopedOutput
from conans.client.source import complete_recipe_sources
from conans.model.ref import ConanFileReference, PackageReference
from conans.errors import NotFoundException, RecipeNotFoundException
from multiprocessing.pool import ThreadPool


def download(app, ref, package_ids, remote, recipe, recorder, remotes):
    out, remote_manager, cache, loader = app.out, app.remote_manager, app.cache, app.loader
    hook_manager = app.hook_manager
    assert(isinstance(ref, ConanFileReference))
    output = ScopedOutput(str(ref), out)

    hook_manager.execute("pre_download", reference=ref, remote=remote)

    try:
        ref = remote_manager.get_recipe(ref, remote)
    except NotFoundException:
        raise RecipeNotFoundException(ref)

    with cache.package_layout(ref).update_metadata() as metadata:
        metadata.recipe.remote = remote.name

    conan_file_path = cache.package_layout(ref).conanfile()
    conanfile = loader.load_basic(conan_file_path)

    # Download the sources too, don't be lazy
    complete_recipe_sources(remote_manager, cache, conanfile, ref, remotes)

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
    short_paths = conanfile.short_paths

    def _download(package_id):
        pref = PackageReference(ref, package_id)
        layout = cache.package_layout(pref.ref, short_paths=short_paths)
        if output and not output.is_terminal:
            output.info("Downloading %s" % str(pref))
        remote_manager.get_package(conanfile, pref, layout, remote, output, recorder)

    if parallel is not None:
        output.info("Downloading binary packages in %s parallel threads" % parallel)
        thread_pool = ThreadPool(parallel)
        thread_pool.map(_download, [package_id for package_id in package_ids])
        thread_pool.close()
        thread_pool.join()
    else:
        for package_id in package_ids:
            _download(package_id)
