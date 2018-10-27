from contextlib import contextmanager

from conans.model.package_metadata import PackageMetadata


def get_recipe_revision(conan_ref, client_cache):
    metadata = _load_metadata(conan_ref, client_cache)
    return metadata.recipe.revision


def get_package_revision(package_ref, client_cache):
    metadata = _load_metadata(package_ref.conan, client_cache)
    return metadata.packages[package_ref.package_id].revision


def get_recipe_revision_from_package(package_ref, client_cache):
    metadata = _load_metadata(package_ref.conan, client_cache)
    return metadata.packages[package_ref.package_id].recipe_revision


def save_recipe_revision(conan_ref, client_cache, revision):
    metadata = _load_metadata(conan_ref, client_cache)
    metadata.recipe.revision = revision
    client_cache.save_package_metadata(conan_ref, metadata)


def save_package_revision(package_ref, client_cache, recipe_revision, revision):
    with update_metadata(package_ref.conan, client_cache) as metadata:
        metadata.packages[package_ref.package_id].recipe_revision = recipe_revision
        metadata.packages[package_ref.package_id].revision = revision


@contextmanager
def update_metadata(conan_ref, client_cache):
    metadata = _load_metadata(conan_ref, client_cache)
    yield metadata
    client_cache.save_package_metadata(conan_ref, metadata)


def _load_metadata(conan_ref, client_cache):
    try:
        return client_cache.load_package_metadata(conan_ref)
    except IOError:
        return PackageMetadata()
