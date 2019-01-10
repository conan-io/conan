import os

from conans.errors import NotFoundException
from conans.model.manifest import discarded_file
from conans.model.ref import PackageReference
from conans.util.files import load


def get_path(cache, ref, package_id, path):
    """
    :param cache: Conan's client cache
    :param ref: Specified reference in the conan get command
    :param package_id: Specified package id (can be None)
    :param path: Path to a file, subfolder of exports (if only ref)
                 or package (if package_id defined)
    :return: The real path in the local cache for the specified parameters
    """
    if package_id is None:  # Get the file in the exported files
        folder = cache.export(ref)
    else:
        folder = cache.package(PackageReference(ref, package_id), short_paths=None)

    abs_path = os.path.join(folder, path)
    if not os.path.exists(abs_path):
        raise NotFoundException("The specified path doesn't exist")
    if os.path.isdir(abs_path):
        return sorted([path for path in os.listdir(abs_path) if not discarded_file(path)])
    else:
        return load(abs_path)
