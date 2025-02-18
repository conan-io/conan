import os

import fasteners

from conan.internal.errors import NotFoundException
from conans.util.files import rmdir
from conans.server.utils.files import path_exists, relative_dirs


class ServerDiskAdapter:
    """Manage access to disk files with common methods required
    for conan operations"""
    def __init__(self, base_url, base_storage_path):
        """
        :param base_url Base url for generate urls to download and upload operations"""

        self.base_url = base_url
        # URLs are generated removing this base path
        self._store_folder = base_storage_path

    def get_file_list(self, absolute_path=""):
        if not path_exists(absolute_path, self._store_folder):
            raise NotFoundException("")
        paths = relative_dirs(absolute_path)
        abs_paths = [os.path.join(absolute_path, relpath) for relpath in paths]
        return abs_paths

    def delete_folder(self, path):
        """Delete folder from disk. Path already contains base dir"""
        if not path_exists(path, self._store_folder):
            raise NotFoundException("")
        rmdir(path)

    def path_exists(self, path):
        return os.path.exists(path)

    def read_file(self, path, lock_file):
        with fasteners.InterProcessLock(lock_file):
            with open(path) as f:
                return f.read()

    def write_file(self, path, contents, lock_file):
        with fasteners.InterProcessLock(lock_file):
            with open(path, "w") as f:
                f.write(contents)
