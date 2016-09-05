'''Adapter for access to S3 filesystem.'''
import os
from abc import ABCMeta, abstractmethod
from conans.errors import NotFoundException
from conans.util.files import relative_dirs, rmdir, md5sum, decode_text
from conans.util.files import path_exists
from conans.paths import SimplePaths


class ServerStorageAdapter(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_download_urls(self, paths, user=None):
        raise NotImplementedError()

    @abstractmethod
    def get_upload_urls(self, paths_sizes, user=None):
        raise NotImplementedError()

    @abstractmethod
    def get_snapshot(self, absolute_path="", files_subset=None):
        raise NotImplementedError()

    @abstractmethod
    def delete_folder(self, path):
        raise NotImplementedError()

    @abstractmethod
    def delete_empty_dirs(self, deleted_refs):
        raise NotImplementedError()


class ServerDiskAdapter(ServerStorageAdapter):
    '''Manage access to disk files with common methods required
    for conan operations'''
    def __init__(self, base_url, base_storage_path, updown_auth_manager):
        """
        :param: base_url Base url for generate urls to download and upload operations"""

        self.base_url = base_url
        # URLs are generated removing this base path
        self.updown_auth_manager = updown_auth_manager
        self._store_folder = base_storage_path

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

    def get_snapshot(self, absolute_path="", files_subset=None):
        """returns a dict with the filepaths and md5"""
        if not path_exists(absolute_path, self._store_folder):
            raise NotFoundException("")
        paths = relative_dirs(absolute_path)
        if files_subset is not None:
            paths = set(paths).intersection(set(files_subset))
        abs_paths = [os.path.join(absolute_path, relpath) for relpath in paths]
        return {filepath: md5sum(filepath) for filepath in abs_paths}

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
        for ref in deleted_refs:
            ref_path = paths.conan(ref)
            for _ in range(4):
                if os.path.exists(ref_path):
                    try:  # Take advantage that os.rmdir does not delete non-empty dirs
                        os.rmdir(ref_path)
                    except OSError:
                        break  # not empty
                ref_path = os.path.dirname(ref_path)
