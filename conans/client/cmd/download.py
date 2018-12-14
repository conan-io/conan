from conans.client.output import ScopedOutput
from conans.client.source import complete_recipe_sources
from conans.errors import NotFoundException
from conans.model.ref import ConanFileReference, PackageReference


def download(reference, package_ids, remote_name, recipe, remote_manager,
             client_cache, out, recorder, loader, hook_manager):

    assert(isinstance(reference, ConanFileReference))
    output = ScopedOutput(str(reference), out)
    registry = client_cache.registry
    remote = registry.remotes.get(remote_name) if remote_name else registry.remotes.default

    hook_manager.execute("pre_download", reference=reference, remote=remote)
    # First of all download package recipe
    try:
        remote_manager.get_recipe(reference, remote)
    except NotFoundException:
        raise NotFoundException("'%s' not found in remote '%s'" % (str(reference), remote.name))
    registry.refs.set(reference, remote.name)
    conan_file_path = client_cache.conanfile(reference)
    conanfile = loader.load_class(conan_file_path)

    if not recipe:  # Not only the recipe
        # Download the sources too, don't be lazy
        complete_recipe_sources(remote_manager, client_cache, conanfile, reference)

        if not package_ids:  # User didnt specify a specific package binary
            output.info("Getting the complete package list from '%s'..." % str(reference))
            packages_props = remote_manager.search_packages(remote, reference, None)
            package_ids = list(packages_props.keys())
            if not package_ids:
                output.warn("No remote binary packages found in remote")

        _download_binaries(conanfile, reference, package_ids, client_cache, remote_manager,
                           remote, output, recorder)
    hook_manager.execute("post_download", conanfile_path=conan_file_path, reference=reference,
                         remote=remote)


def _download_binaries(conanfile, reference, package_ids, client_cache, remote_manager, remote,
                       output, recorder):
    short_paths = conanfile.short_paths

    for package_id in package_ids:
        package_ref = PackageReference(reference, package_id)
        package_folder = client_cache.package(package_ref, short_paths=short_paths)
        output.info("Downloading %s" % str(package_ref))
        remote_manager.get_package(package_ref, package_folder, remote, output, recorder)
