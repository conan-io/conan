from os.path import normpath, join, relpath
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import SimplePaths, EXPORT_FOLDER, PACKAGES_FOLDER


class ServerStore(SimplePaths):

    def __init__(self, storage_adapter):
        super(ServerStore, self).__init__(storage_adapter.base_storage_folder())
        self._storage_adapter = storage_adapter

    def conan(self, reference, resolve_latest=True):  # Ignored in non-revisions, but hard to remove
        return normpath(join(self.store, "/".join(reference)))

    def packages(self, reference):
        return join(self.conan(reference), PACKAGES_FOLDER)

    def package(self, p_reference, short_paths=None):
        return join(self.packages(p_reference.conan), p_reference.package_id)

    def export(self, reference):
        return join(self.conan(reference), EXPORT_FOLDER)

    def get_conanfile_file_path(self, reference, filename):
        abspath = join(self.export(reference), filename)
        return abspath

    def get_package_file_path(self, p_reference, filename):
        p_path = self.package(p_reference)
        abspath = join(p_path, filename)
        return abspath

    def path_exists(self, path):
        return self._storage_adapter.path_exists(path)

    # ############ SNAPSHOTS (APIv1)
    def get_recipe_snapshot(self, reference):
        """Returns a {filepath: md5} """
        assert isinstance(reference, ConanFileReference)
        return self._get_snapshot_of_files(self.export(reference))

    def get_package_snapshot(self, p_reference):
        """Returns a {filepath: md5} """
        assert isinstance(p_reference, PackageReference)
        path = self.package(p_reference)
        return self._get_snapshot_of_files(path)

    def _get_snapshot_of_files(self, relative_path):
        snapshot = self._storage_adapter.get_snapshot(relative_path)
        snapshot = self._relativize_keys(snapshot, relative_path)
        return snapshot

    # ############ ONLY FILE LIST SNAPSHOTS (APIv2)
    def get_recipe_file_list(self, reference):
        """Returns a {filepath: md5} """
        assert isinstance(reference, ConanFileReference)
        return self._get_file_list(self.export(reference))

    def get_package_file_list(self, p_reference):
        """Returns a {filepath: md5} """
        assert isinstance(p_reference, PackageReference)
        return self._get_file_list(self.package(p_reference))

    def _get_file_list(self, relative_path):
        file_list = self._storage_adapter.get_file_list(relative_path)
        file_list = [relpath(old_key, relative_path) for old_key in file_list]
        return file_list

    # ######### DELETE (APIv1 and APIv2)
    def remove_conanfile(self, reference):
        assert isinstance(reference, ConanFileReference)
        result = self._storage_adapter.delete_folder(self.conan(reference))
        self._storage_adapter.delete_empty_dirs([reference])
        return result

    def remove_packages(self, reference, package_ids_filter):
        assert isinstance(reference, ConanFileReference)
        assert isinstance(package_ids_filter, list)

        if not package_ids_filter:  # Remove all packages
            packages_folder = self.packages(reference)
            self._storage_adapter.delete_folder(packages_folder)
        else:
            for package_id in package_ids_filter:
                package_ref = PackageReference(reference, package_id)
                package_folder = self.package(package_ref)
                self._storage_adapter.delete_folder(package_folder)
        self._storage_adapter.delete_empty_dirs([reference])
        return

    def remove_conanfile_files(self, reference, files):
        subpath = self.export(reference)
        for filepath in files:
            path = join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    def remove_package_files(self, package_reference, files):
        subpath = self.package(package_reference)
        for filepath in files:
            path = join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    # ONLY APIv1 URLS

    # ############ DOWNLOAD URLS
    def get_download_conanfile_urls(self, reference, files_subset=None, user=None):
        """Returns a {filepath: url} """
        assert isinstance(reference, ConanFileReference)
        return self._get_download_urls(self.export(reference), files_subset, user)

    def get_download_package_urls(self, package_reference, files_subset=None, user=None):
        """Returns a {filepath: url} """
        assert isinstance(package_reference, PackageReference)
        return self._get_download_urls(self.package(package_reference), files_subset, user)

    # ############ UPLOAD URLS
    def get_upload_conanfile_urls(self, reference, filesizes, user):
        """
        :param reference: ConanFileReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(reference, ConanFileReference)
        assert isinstance(filesizes, dict)
        return self._get_upload_urls(self.export(reference), filesizes, user)

    def get_upload_package_urls(self, package_reference, filesizes, user):
        """
        :param reference: PackageReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(package_reference, PackageReference)
        assert isinstance(filesizes, dict)
        return self._get_upload_urls(self.package(package_reference), filesizes, user)

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
            abs_paths[join(relative_path, path)] = filesize
        urls = self._storage_adapter.get_upload_urls(abs_paths, user)
        urls = self._relativize_keys(urls, relative_path)
        return urls

    @staticmethod
    def _relativize_keys(the_dict, basepath):
        """Relativize the keys in the dict relative to basepath"""
        ret = {}
        for old_key, value in the_dict.items():
            new_key = relpath(old_key, basepath)
            ret[new_key] = value
        return ret
