import os
from conans.paths import SimplePaths
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.store.disk_adapter import ServerStorageAdapter


class FileManager(object):
    '''Coordinate the paths and the storage_adapter to get
    access to required elements in storage.

    This class doesn't handle permissions.'''

    def __init__(self, paths, storage_adapter):
        assert isinstance(paths, SimplePaths)
        assert isinstance(storage_adapter, ServerStorageAdapter)
        self.paths = paths
        self._storage_adapter = storage_adapter

    # ############ SNAPSHOTS
    def get_recipe(self, conan_reference):
        conanfile_path = self.paths.conanfile(conan_reference)
        return self._storage_adapter.get_file(conanfile_path)

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
        result = self._storage_adapter.delete_folder(self.paths.conan(reference))
        self._storage_adapter.delete_empty_dirs([reference])
        return result

    def remove_packages(self, reference, package_ids_filter):
        assert isinstance(reference, ConanFileReference)
        assert isinstance(package_ids_filter, list)

        if not package_ids_filter:  # Remove all packages
            packages_folder = self.paths.packages(reference)
            self._storage_adapter.delete_folder(packages_folder)
        else:
            for package_id in package_ids_filter:
                package_ref = PackageReference(reference, package_id)
                package_folder = self.paths.package(package_ref)
                self._storage_adapter.delete_folder(package_folder)
        self._storage_adapter.delete_empty_dirs([reference])
        return

    def remove_conanfile_files(self, reference, files):
        subpath = self.paths.export(reference)
        for filepath in files:
            path = os.path.join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    def remove_package_files(self, package_reference, files):
        subpath = self.paths.package(package_reference)
        for filepath in files:
            path = os.path.join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    # ############ INTERNAL METHODS
    def _get_snapshot_of_files(self, relative_path):
        snapshot = self._storage_adapter.get_snapshot(relative_path)
        snapshot = self._relativize_keys(snapshot, relative_path)
        return snapshot

    def _get_download_urls(self, relative_path, files_subset=None, user=None):
        """Get the download urls for the whole relative_path or just
        for a subset of files. files_subset has to be a list with paths
        relative to relative_path"""
        relative_snap = self._storage_adapter.get_snapshot(relative_path, files_subset)
        urls = self._storage_adapter.get_download_urls(list(relative_snap.keys()), user)
        urls = self._relativize_keys(urls, relative_path)
        return urls

    def _get_upload_urls(self, relative_path, filesizes, user=None):
        abs_paths = {}
        for path, filesize in filesizes.items():
            abs_paths[os.path.join(relative_path, path)] = filesize
        urls = self._storage_adapter.get_upload_urls(abs_paths, user)
        urls = self._relativize_keys(urls, relative_path)
        return urls

    def _relativize_keys(self, the_dict, basepath):
        """Relativize the keys in the dict relative to basepath"""
        ret = {}
        for old_key, value in the_dict.items():
            new_key = os.path.relpath(old_key, basepath)
            ret[new_key] = value
        return ret
