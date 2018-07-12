from os.path import normpath, join, relpath

from conans.errors import NotFoundException
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import SimplePaths, EXPORT_FOLDER, PACKAGES_FOLDER

LAST_REVISION_FILE = "last_rev.txt"


class ServerStore(SimplePaths):

    def __init__(self, revisions_enabled, storage_adapter):
        super(ServerStore, self).__init__(storage_adapter.base_storage_folder())
        self._revisions_enabled = revisions_enabled
        self._storage_adapter = storage_adapter

    # Methods to override some basics from paths to allow revisions paths (reading latest)
    def conan(self, reference):
        reference = self.ref_with_rev(reference)
        tmp = normpath(join(self.store, "/".join(reference)))
        if reference.revision:
            return join(tmp, reference.revision)
        return tmp

    def packages(self, reference):
        reference = self.ref_with_rev(reference)
        return join(self.conan(reference), PACKAGES_FOLDER)

    def package(self, p_reference, short_paths=None):
        p_reference = self._patch_package_ref(p_reference)
        tmp = join(self.packages(p_reference.conan), p_reference.package_id)
        if p_reference.revision:
            return join(tmp, p_reference.revision)
        return tmp

    def export(self, reference):
        return join(self.conan(reference), EXPORT_FOLDER)

    # Methods to manage revisions
    def get_last_revision(self, reference):
        assert(isinstance(reference, ConanFileReference))
        rev_file = self._last_revision_path(reference)
        if self._storage_adapter.path_exists(rev_file):
            return self._storage_adapter.read_file(rev_file, lock_file=rev_file + ".lock")
        else:
            return None

    def update_last_revision(self, reference):
        assert(isinstance(reference, ConanFileReference))
        rev_file = self._last_revision_path(reference)
        self._storage_adapter.write_file(rev_file, reference.revision, lock_file=rev_file + ".lock")

    def get_last_package_revision(self, p_reference):
        assert(isinstance(p_reference, PackageReference))
        rev_file = self._last_package_revision_path(p_reference)
        if self._storage_adapter.path_exists(rev_file):
            return self._storage_adapter.read_file(rev_file, lock_file=rev_file + ".lock")
        else:
            return None

    def update_last_package_revision(self, p_reference):
        assert(isinstance(p_reference, PackageReference))
        rev_file = self._last_package_revision_path(p_reference)
        self._storage_adapter.write_file(rev_file, p_reference.revision,
                                         lock_file=rev_file + ".lock")

    def _last_revision_path(self, reference):
        recipe_folder = normpath(join(self._store_folder, "/".join(reference)))
        return join(recipe_folder, LAST_REVISION_FILE)

    def _last_package_revision_path(self, p_reference):
        tmp = normpath(join(self._store_folder, "/".join(p_reference.conan)))
        revision = {None: ""}.get(p_reference.conan.revision, p_reference.conan.revision)
        p_folder = join(tmp, revision, PACKAGES_FOLDER, p_reference.package_id)
        return join(p_folder, LAST_REVISION_FILE)

    def get_conanfile_file_path(self, reference, filename):
        reference = self.ref_with_rev(reference)
        abspath = join(self.export(reference), filename)
        return abspath

    def get_package_file_path(self, p_reference, filename):
        p_reference = self._patch_package_ref(p_reference)
        p_path = self.package(p_reference)
        abspath = join(p_path, filename)
        return abspath

    def ref_with_rev(self, reference):
        if not self._revisions_enabled:
            return reference.copy_without_revision()
        if reference.revision:
            return reference

        latest = self.get_last_revision(reference)
        if not latest:
            raise NotFoundException("Recipe not found: '%s'" % reference.full_repr())

        reference.revision = latest
        return reference

    def _patch_package_ref(self, p_reference):
        if not self._revisions_enabled:
            return p_reference.copy_without_revision()
        if p_reference.revision:
            return p_reference

        latest = self.get_last_package_revision(p_reference)
        if not latest:
            raise NotFoundException("Package not found: '%s'" % str(p_reference))

        reference = self.ref_with_rev(p_reference.conan)
        ret = PackageReference(reference, p_reference.package_id)
        ret.revision = latest
        return ret

    def update_recipe_revision(self, reference):
        if not self._revisions_enabled:
            return

        self.update_last_revision(reference)

    def update_package_revision(self, p_reference):
        if not self._revisions_enabled:
            return

        self.update_last_package_revision(p_reference)

    # ############ SNAPSHOTS (APIv1 and APIv2)
    def get_conanfile_snapshot(self, reference):
        """Returns a {filepath: md5} """
        assert isinstance(reference, ConanFileReference)
        return self._get_snapshot_of_files(self.export(reference))

    def get_package_snapshot(self, p_reference):
        """Returns a {filepath: md5} """
        assert isinstance(p_reference, PackageReference)
        p_reference = self._patch_package_ref(p_reference)
        path = self.package(p_reference)
        return self._get_snapshot_of_files(path)

    def _get_snapshot_of_files(self, relative_path):
        snapshot = self._storage_adapter.get_snapshot(relative_path)
        snapshot = self._relativize_keys(snapshot, relative_path)
        return snapshot

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
