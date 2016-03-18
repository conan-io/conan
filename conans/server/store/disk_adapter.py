'''Adapter for access to S3 filesystem.'''
import os
from conans.errors import NotFoundException
from conans.server.store.file_manager import StorageAdapter
from conans.util.files import relative_dirs, rmdir, load, md5sum
from conans.util.files import path_exists


class DiskAdapter(StorageAdapter):
    '''Manage access to disk files with common methods required
    for conan operations'''
    def __init__(self, base_url, base_storage_path, updown_auth_manager):
        """
        :param: base_url Base url for generate urls to download and upload operations"""

        self.base_url = base_url
        # URLs are generated removing this base path
        self.base_storage_path = base_storage_path
        self.updown_auth_manager = updown_auth_manager

    def get_download_urls(self, paths, user=None):
        '''Get the urls for download the specified files using s3 signed request.
        returns a dict with this structure: {"filepath": "http://..."}

        paths is a list of path files '''

        assert isinstance(paths, list)
        ret = {}
        for filepath in paths:
            url_path = os.path.relpath(filepath, self.base_storage_path)
            url_path = url_path.replace("\\", "/")
            # FALTA SIZE DEL FICHERO PARA EL UPLOAD URL!
            signature = self.updown_auth_manager.get_token_for(url_path, user)
            url = "%s/%s?signature=%s" % (self.base_url, url_path, signature.decode())
            ret[filepath] = url

        return ret

    def get_upload_urls(self, paths_sizes, user=None):
        '''Get the urls for upload the specified files using s3 signed request.
        returns a dict with this structure: {"filepath": "http://..."}

        paths_sizes is a dict of {path: size_in_bytes} '''
        assert isinstance(paths_sizes, dict)
        ret = {}
        for filepath, filesize in paths_sizes.items():
            url_path = os.path.relpath(filepath, self.base_storage_path)
            url_path = url_path.replace("\\", "/")
            # FALTA SIZE DEL FICHERO PARA EL UPLOAD URL!
            signature = self.updown_auth_manager.get_token_for(url_path, user, filesize)
            url = "%s/%s?signature=%s" % (self.base_url, url_path, signature.decode())
            ret[filepath] = url

        return ret

    def get_snapshot(self, absolute_path="", files_subset=None):
        """returns a dict with the filepaths and md5"""
        if not path_exists(absolute_path, self.base_storage_path):
            raise NotFoundException()
        paths = relative_dirs(absolute_path)
        if files_subset is not None:
            paths = set(paths).intersection(set(files_subset))
        abs_paths = [os.path.join(absolute_path, relpath) for relpath in paths]
        return {filepath: md5sum(filepath) for filepath in abs_paths}

    def delete_folder(self, path):
        '''Delete folder from disk. Path already contains base dir'''
        if not path_exists(path, self.base_storage_path):
            raise NotFoundException()
        rmdir(path)

    def delete_file(self, path):
        '''Delete files from bucket. Path already contains base dir'''
        if not path_exists(path, self.base_storage_path):
            raise NotFoundException()
        os.remove(path)

    # ######### FOR SEARCH
    def list_folder_subdirs(self, basedir="", level=None):
        ret = []
        for root, dirs, _ in os.walk(basedir):
            rel_path = os.path.relpath(root, basedir)
            if rel_path == ".":
                continue
            dir_split = rel_path.split(os.sep)
            if level is not None:
                if len(dir_split) == level:
                    ret.append("/".join(dir_split))
                    dirs[:] = []  # Stop iterate subdirs
            else:
                ret.append("/".join(dir_split))
        return ret

    # ######### FOR SEARCH
    def get_file(self, filepath):
        """path already contains the base_storage_path
        (obtained through paths object)"""
        if not path_exists(filepath, self.base_storage_path):
            raise NotFoundException()
        return load(filepath)
