from conans.client.output import ScopedOutput
from conans.client.source import complete_recipe_sources
from conans.model.ref import ConanFileReference, PackageReference
from conans.errors import NotFoundException, RecipeNotFoundException


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

    layout = cache.package_layout(ref)
    with layout.update_metadata() as metadata:
        metadata.recipe.remote = remote.name

    conan_file_path = layout.conanfile()
    conanfile = loader.load_basic(conan_file_path)
    layout.short_paths = conanfile.short_paths

    # Download the sources too, don't be lazy
    complete_recipe_sources(remote_manager, cache, conanfile, ref, remotes)

    if not recipe:  # Not only the recipe
        if not package_ids:  # User didn't specify a specific package binary
            output.info("Getting the complete package list from '%s'..." % ref.full_str())
            packages_props = remote_manager.search_packages(remote, ref, None)
            package_ids = list(packages_props.keys())
            if not package_ids:
                output.warn("No remote binary packages found in remote")

        _download_binaries(layout, ref, package_ids, remote_manager, remote, output, recorder)
    hook_manager.execute("post_download", conanfile_path=conan_file_path, reference=ref,
                         remote=remote)


def _download_binaries(layout, ref, package_ids, remote_manager, remote, output,
                       recorder):
    for package_id in package_ids:
        pref = PackageReference(ref, package_id)
        package_folder = layout.package(pref)
        if output and not output.is_terminal:
            output.info("Downloading %s" % str(pref))
        remote_manager.get_package(pref, package_folder, remote, output, recorder)
