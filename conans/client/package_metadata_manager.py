from contextlib import contextmanager

from conans.model.package_metadata import PackageMetadata
from conans.server.conf import DEFAULT_REVISION_V1


def get_recipe_revision(conan_ref, client_cache):
    metadata = _load_metadata(conan_ref, client_cache)
    return metadata.recipe.revision or DEFAULT_REVISION_V1


def get_package_revision(package_ref, client_cache):
    metadata = _load_metadata(package_ref.conan, client_cache)
    return metadata.packages[package_ref.package_id].revision or DEFAULT_REVISION_V1


def get_recipe_revision_from_package(package_ref, client_cache):
    metadata = _load_metadata(package_ref.conan, client_cache)
    return metadata.packages[package_ref.package_id].recipe_revision or DEFAULT_REVISION_V1


def save_recipe_revision(conan_ref, client_cache, revision, rev_time):
    if not revision:  # Will read DEFAULT_REVISION_V1 anyway
        return
    metadata = _load_metadata(conan_ref, client_cache)
    metadata.recipe.revision = revision or DEFAULT_REVISION_V1
    metadata.recipe.time = rev_time
    client_cache.save_package_metadata(conan_ref, metadata)


def save_package_revision(package_ref, client_cache, recipe_revision, revision, rev_time):
    if not revision:  # Will read DEFAULT_REVISION_V1 anyway
        return
    with update_metadata(package_ref.conan, client_cache) as metadata:
        metadata.packages[package_ref.package_id].recipe_revision = recipe_revision
        metadata.packages[package_ref.package_id].revision = revision
        metadata.packages[package_ref.package_id].time = rev_time


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
