import os
from contextlib import contextmanager

import fasteners

from conans.errors import NotFoundException
from conans.util.files import md5sum, rmdir
from conans.server.utils.files import path_exists, relative_dirs


@contextmanager
def no_op():
    yield


class ServerDiskAdapter(object):
    """Manage access to disk files with common methods required
    for conan operations"""
    def __init__(self, base_url, base_storage_path):
        """
        :param base_url Base url for generate urls to download and upload operations"""

        self.base_url = base_url
        # URLs are generated removing this base path
        self._store_folder = base_storage_path

    def _get_paths(self, absolute_path, files_subset):
        if not path_exists(absolute_path, self._store_folder):
            raise NotFoundException("")
        paths = relative_dirs(absolute_path)
        if files_subset is not None:
            paths = set(paths).intersection(set(files_subset))
        abs_paths = [os.path.join(absolute_path, relpath) for relpath in paths]
        return abs_paths

    def get_snapshot(self, absolute_path="", files_subset=None):
        """returns a dict with the filepaths and md5"""
        abs_paths = self._get_paths(absolute_path, files_subset)
        return {filepath: md5sum(filepath) for filepath in abs_paths}

    def get_file_list(self, absolute_path="", files_subset=None):
        abs_paths = self._get_paths(absolute_path, files_subset)
        return abs_paths

    def delete_folder(self, path):
        """Delete folder from disk. Path already contains base dir"""
        if not path_exists(path, self._store_folder):
            raise NotFoundException("")
        rmdir(path)

    def delete_file(self, path):
        """Delete files from bucket. Path already contains base dir"""
        if not path_exists(path, self._store_folder):
            raise NotFoundException("")
        os.remove(path)

    def path_exists(self, path):
        return os.path.exists(path)

    def read_file(self, path, lock_file):
        with fasteners.InterProcessLock(lock_file) if lock_file else no_op():
            with open(path) as f:
                return f.read()

    def write_file(self, path, contents, lock_file):
        with fasteners.InterProcessLock(lock_file) if lock_file else no_op():
            with open(path, "w") as f:
                f.write(contents)

    def base_storage_folder(self):
        return self._store_folder
