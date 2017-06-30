import os

from conans.errors import NotFoundException
from conans.model.ref import PackageReference
from conans.util.files import load


class LocalFileGetter(object):

    def __init__(self, client_cache):
        self._client_cache = client_cache

    def get_path(self, conan_ref, package_id, path):
        if package_id is None:  # Get the file in the exported files
            folder = self._client_cache.export(conan_ref)
        else:
            folder = self._client_cache.package(PackageReference(conan_ref, package_id))

        abs_path = os.path.join(folder, path)
        if not os.path.exists(abs_path):
            raise NotFoundException("The specified path doesn't exist")
        if os.path.isdir(abs_path):
            return os.listdir(abs_path)
        else:
            return load(abs_path)
