from conans.paths import SimplePaths, CONANINFO
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.info import SearchInfo
from conans.model.info import ConanInfo


from abc import ABCMeta, abstractmethod
from conans.util.log import logger
from conans.errors import ConanException
import traceback
from conans.util.files import delete_empty_dirs


class StorageAdapter:
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

    # ######### FOR SEARCH
    @abstractmethod
    def list_folder_subdirs(self, basedir=None, level=None):
        raise NotImplementedError()

    @abstractmethod
    def get_file(self, filepath):
        raise NotImplementedError()


class FileManager(object):
    '''Coordinate the paths and the file_adapter to get
    access to required elements in disk storage.

    This class doesn't handle permissions.'''

    def __init__(self, paths, file_adapter, search_engine=None):
        assert isinstance(paths, SimplePaths)
        self.paths = paths
        self._file_adapter = file_adapter
        # If search_engine is specified, conans will be searched
        # using the search engine
        self._search_engine = search_engine

    # ############ SNAPSHOTS
    def get_conanfile_snapshot(self, reference):
        """Returns a {filepath: md5} """
        assert isinstance(reference, ConanFileReference)
        return self._get_snapshot_of_files(self.paths.export(reference))

    def get_package_snapshot(self, package_reference):
        """Returns a {filepath: md5} """
        assert isinstance(package_reference, PackageReference)
        path = self.paths.package(package_reference)
        return self._get_snapshot_of_files(path)

    # ############ DOWNLOAD URLS
    def get_download_conanfile_urls(self, reference, files_subset=None, user=None):
        """Returns a {filepath: url} """
        assert isinstance(reference, ConanFileReference)
        return self._get_download_urls(self.paths.export(reference), files_subset, user)

    def get_download_package_urls(self, package_reference, files_subset=None, user=None):
        """Returns a {filepath: url} """
        assert isinstance(package_reference, PackageReference)
        return self._get_download_urls(self.paths.package(package_reference), files_subset, user)

    # ############ UPLOAD URLS
    def get_upload_conanfile_urls(self, reference, filesizes, user):
        """
        :param reference: ConanFileReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(reference, ConanFileReference)
        assert isinstance(filesizes, dict)
        return self._get_upload_urls(self.paths.export(reference), filesizes, user)

    def get_upload_package_urls(self, package_reference, filesizes, user):
        """
        :param reference: PackageReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(package_reference, PackageReference)
        assert isinstance(filesizes, dict)
        return self._get_upload_urls(self.paths.package(package_reference), filesizes, user)

    # ######### DELETE
    def remove_conanfile(self, reference):
        assert isinstance(reference, ConanFileReference)
        result = self._file_adapter.delete_folder(self.paths.conan(reference))
        delete_empty_dirs(self.paths.store)
        return result

    def remove_packages(self, reference, package_ids_filter):
        assert isinstance(reference, ConanFileReference)
        assert isinstance(package_ids_filter, list)

        if not package_ids_filter:  # Remove all packages
            packages_folder = self.paths.packages(reference)
            self._file_adapter.delete_folder(packages_folder)
        else:
            for package_id in package_ids_filter:
                package_ref = PackageReference(reference, package_id)
                package_folder = self.paths.package(package_ref)
                self._file_adapter.delete_folder(package_folder)
        delete_empty_dirs(self.paths.store)
        return

    def remove_conanfile_files(self, reference, files):
        subpath = self.paths.export(reference)
        for filepath in files:
            path = os.path.join(subpath, filepath)
            self._file_adapter.delete_file(path)

    def remove_package_files(self, package_reference, files):
        subpath = self.paths.package(package_reference)
        for filepath in files:
            path = os.path.join(subpath, filepath)
            self._file_adapter.delete_file(path)

    # ######### SEARCH
    def search(self, pattern=None, ignorecase=True, exclude_index=False):
        """ Get all an info dict from your exported conans
        param paths: ConanPaths object
        param pattern: these could be conan_reference or wildcards, e.g., "opencv/*"
        """
        if not self._search_engine or exclude_index:
            result = SearchInfo()
            conans = self._exported_conans(pattern, ignorecase)
            for conan_reference in conans:
                result[conan_reference] = self._single_conan_search(conan_reference)
        else:
            # We have a quick index for search conanfiles
            try:
                return self._search_engine.search_conanfiles(pattern)[1]
            except Exception as exc:
                logger.error(exc)
                logger.error(traceback.format_exc())
                raise ConanException("Something went bad with the search. Please try again later.")

        return result

    def _exported_conans(self, pattern=None, ignorecase=True):
        """ Returns a list of exported ConanFileReference
            The pattern is case insensitive by default
        """
        from fnmatch import translate
        import re
        if pattern:
            pattern = translate(pattern)
            pattern = re.compile(pattern, re.IGNORECASE) if ignorecase else re.compile(pattern)

        subdirs = self._file_adapter.list_folder_subdirs(basedir=self.paths.store, level=4)

        if not pattern:
            return [ConanFileReference(*folder.split("/")) for folder in subdirs]
        else:
            ret = []
            for subdir in subdirs:
                conan_ref = ConanFileReference(*subdir.split("/"))
                if pattern:
                    if pattern.match(str(conan_ref)):
                        ret.append(conan_ref)
            return ret

    def _single_conan_search(self, conan_ref):
        """ Return a dict like this:

                {package_ID: {name: "OpenCV",
                               version: "2.14",
                               settings: {os: Windows}}}
        param conan_ref: ConanFileReference object
        """
        result = {}
        packages_path = self.paths.packages(conan_ref)
        subdirs = self._file_adapter.list_folder_subdirs(packages_path, level=1)
        for package_id in subdirs:
            try:
                package_reference = PackageReference(conan_ref, package_id)
                info_path = os.path.join(self.paths.package(package_reference), CONANINFO)
                conan_info_content = self._file_adapter.get_file(info_path)
                conan_vars_info = ConanInfo.loads(conan_info_content)
                result[package_id] = conan_vars_info
            except Exception as exc:
                logger.error("Package %s has not ConanInfo file" % str(package_reference))
                if str(exc):
                    logger.error(str(exc))

        return result

    # ############ INTERNAL METHODS
    def _get_snapshot_of_files(self, relative_path):
        snapshot = self._file_adapter.get_snapshot(relative_path)
        snapshot = self._relativize_keys(snapshot, relative_path)
        return snapshot

    def _get_download_urls(self, relative_path, files_subset=None, user=None):
        """Get the download urls for the whole relative_path or just
        for a subset of files. files_subset has to be a list with paths
        relative to relative_path"""
        relative_snap = self._file_adapter.get_snapshot(relative_path, files_subset)
        urls = self._file_adapter.get_download_urls(list(relative_snap.keys()), user)
        urls = self._relativize_keys(urls, relative_path)
        return urls

    def _get_upload_urls(self, relative_path, filesizes, user=None):
        abs_paths = {}
        for path, filesize in filesizes.items():
            abs_paths[os.path.join(relative_path, path)] = filesize
        urls = self._file_adapter.get_upload_urls(abs_paths, user)
        urls = self._relativize_keys(urls, relative_path)
        return urls

    def _relativize_keys(self, the_dict, basepath):
        """Relativize the keys in the dict relative to basepath"""
        ret = {}
        for old_key, value in the_dict.items():
            new_key = os.path.relpath(old_key, basepath)
            ret[new_key] = value
        return ret
