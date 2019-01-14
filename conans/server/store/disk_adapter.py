import os

import fasteners

from conans.client.tools.env import no_op
from conans.errors import NotFoundException
from conans.paths.simple_paths import SimplePaths
from conans.server.store.server_store import REVISIONS_FILE
from conans.util.files import decode_text, md5sum, path_exists, relative_dirs, rmdir


class ServerDiskAdapter(object):
    '''Manage access to disk files with common methods required
    for conan operations'''
    def __init__(self, base_url, base_storage_path, updown_auth_manager):
        """
        :param: base_url Base url for generate urls to download and upload operations"""

        self.base_url = base_url
        # URLs are generated removing this base path
        self.updown_auth_manager = updown_auth_manager
        self._store_folder = base_storage_path

    # ONLY USED BY APIV1
    def get_download_urls(self, paths, user=None):
        '''Get the urls for download the specified files using s3 signed request.
        returns a dict with this structure: {"filepath": "http://..."}

        paths is a list of path files '''

        assert isinstance(paths, list)
        ret = {}
        for filepath in paths:
            url_path = os.path.relpath(filepath, self._store_folder)
            url_path = url_path.replace("\\", "/")
            # FALTA SIZE DEL FICHERO PARA EL UPLOAD URL!
            signature = self.updown_auth_manager.get_token_for(url_path, user)
            url = "%s/%s?signature=%s" % (self.base_url, url_path, decode_text(signature))
            ret[filepath] = url

        return ret

    # ONLY USED BY APIV1
    def get_upload_urls(self, paths_sizes, user=None):
        '''Get the urls for upload the specified files using s3 signed request.
        returns a dict with this structure: {"filepath": "http://..."}

        paths_sizes is a dict of {path: size_in_bytes} '''
        assert isinstance(paths_sizes, dict)
        ret = {}
        for filepath, filesize in paths_sizes.items():
            url_path = os.path.relpath(filepath, self._store_folder)
            url_path = url_path.replace("\\", "/")
            # FALTA SIZE DEL FICHERO PARA EL UPLOAD URL!
            signature = self.updown_auth_manager.get_token_for(url_path, user, filesize)
            url = "%s/%s?signature=%s" % (self.base_url, url_path, decode_text(signature))
            ret[filepath] = url

        return ret

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
        '''Delete folder from disk. Path already contains base dir'''
        if not path_exists(path, self._store_folder):
            raise NotFoundException("")
        rmdir(path)

    def delete_file(self, path):
        '''Delete files from bucket. Path already contains base dir'''
        if not path_exists(path, self._store_folder):
            raise NotFoundException("")
        os.remove(path)

    def delete_empty_dirs(self, deleted_refs):
        paths = SimplePaths(self._store_folder)
        lock_files = set([REVISIONS_FILE, "%s.lock" % REVISIONS_FILE])
        for ref in deleted_refs:
            ref_path = paths.conan(ref)
            for _ in range(4 if not ref.revision else 5):
                if os.path.exists(ref_path):
                    if set(os.listdir(ref_path)) == lock_files:
                        for lock_file in lock_files:
                            os.unlink(os.path.join(ref_path, lock_file))
                    try:  # Take advantage that os.rmdir does not delete non-empty dirs
                        os.rmdir(ref_path)
                    except OSError:
                        break  # not empty
                ref_path = os.path.dirname(ref_path)

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
