from os.path import join, normpath, relpath

from conans.errors import ConanException, NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_FOLDER, PACKAGES_FOLDER, SimplePaths
from conans.server.revision_list import RevisionList

REVISIONS_FILE = "revisions.txt"


class ServerStore(SimplePaths):

    def __init__(self, storage_adapter):
        super(ServerStore, self).__init__(storage_adapter.base_storage_folder())
        self._storage_adapter = storage_adapter

    def conan(self, reference, resolve_latest=True):
        reference = self.ref_with_rev(reference) if resolve_latest else reference
        tmp = normpath(join(self.store, reference.dir_repr()))
        return join(tmp, reference.revision) if reference.revision else tmp

    def packages(self, reference):
        reference = self.ref_with_rev(reference)
        return join(self.conan(reference), PACKAGES_FOLDER)

    def package(self, p_reference, short_paths=None):
        p_reference = self.p_ref_with_rev(p_reference)
        tmp = join(self.packages(p_reference.conan), p_reference.package_id)
        return join(tmp, p_reference.revision) if p_reference.revision else tmp

    def export(self, reference):
        return join(self.conan(reference), EXPORT_FOLDER)

    def get_conanfile_file_path(self, reference, filename):
        reference = self.ref_with_rev(reference)
        abspath = join(self.export(reference), filename)
        return abspath

    def get_package_file_path(self, p_reference, filename):
        p_reference = self.p_ref_with_rev(p_reference)
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
        p_reference = self.p_ref_with_rev(p_reference)
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
        result = self._storage_adapter.delete_folder(self.conan(reference, resolve_latest=False))
        if reference.revision:
            self._remove_revision_from_index(reference)
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

    def remove_package(self, package_ref):
        assert isinstance(package_ref, PackageReference)
        assert package_ref.revision is not None
        assert package_ref.conan.revision is not None
        package_folder = self.package(package_ref)
        self._storage_adapter.delete_folder(package_folder)
        self._remove_package_revision_from_index(package_ref)

    def remove_all_packages(self, reference):
        assert reference.revision is not None
        assert isinstance(reference, ConanFileReference)
        packages_folder = self.packages(reference)
        self._storage_adapter.delete_folder(packages_folder)

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

    # Methods to manage revisions
    def get_last_revision(self, reference):
        assert(isinstance(reference, ConanFileReference))
        rev_file_path = self._recipe_revisions_file(reference)
        return self._get_latest_revision(rev_file_path)

    def get_recipe_revisions(self, reference):
        rev_file_path = self._recipe_revisions_file(reference)
        return [reference.copy_with_rev(rev.revision)
                for rev in self._get_revisions(rev_file_path).items()]

    def get_latest_package_reference(self, package_ref):
        assert(isinstance(package_ref, PackageReference))
        rev_file_path = self._recipe_revisions_file(package_ref.conan)
        revs = self._get_revisions(rev_file_path)
        if not revs:
            raise NotFoundException("Recipe not found: '%s'" % str(package_ref.conan))

        for rev in revs.items():
            pref = PackageReference(package_ref.conan.copy_with_rev(rev.revision),
                                    package_ref.package_id)
            tmp = self.get_last_package_revision(pref)
            if tmp:
                pref = pref.copy_with_revs(rev.revision, tmp.revision)
            try:
                folder = self.package(pref)
                if self._storage_adapter.path_exists(folder):
                    return pref
            except NotFoundException:
                pass
        raise NotFoundException("Package not found: '%s'" % str(package_ref))

    def get_last_package_revision(self, p_reference):
        assert(isinstance(p_reference, PackageReference))
        rev_file_path = self._package_revisions_file(p_reference)
        return self._get_latest_revision(rev_file_path)

    def update_last_revision(self, reference):
        assert(isinstance(reference, ConanFileReference))
        rev_file_path = self._recipe_revisions_file(reference)
        self._update_last_revision(rev_file_path, reference)

    def update_last_package_revision(self, p_reference):
        assert(isinstance(p_reference, PackageReference))
        rev_file_path = self._package_revisions_file(p_reference)
        self._update_last_revision(rev_file_path, p_reference)

    def _update_last_revision(self, rev_file_path, reference):
        if self._storage_adapter.path_exists(rev_file_path):
            rev_file = self._storage_adapter.read_file(rev_file_path,
                                                       lock_file=rev_file_path + ".lock")
            rev_list = RevisionList.loads(rev_file)
        else:
            rev_list = RevisionList()
        if reference.revision is None:
            raise ConanException("Invalid revision for: %s" % reference.full_repr())
        rev_list.add_revision(reference.revision)
        self._storage_adapter.write_file(rev_file_path, rev_list.dumps(),
                                         lock_file=rev_file_path + ".lock")

    def get_package_revisions(self, p_reference):
        assert p_reference.conan.revision is not None
        tmp = self._package_revisions_file(p_reference)
        ret = self._get_revisions(tmp)
        return ret.items()

    def _get_revisions(self, rev_file_path):
        if self._storage_adapter.path_exists(rev_file_path):
            rev_file = self._storage_adapter.read_file(rev_file_path,
                                                       lock_file=rev_file_path + ".lock")
            rev_list = RevisionList.loads(rev_file)
            return rev_list
        else:
            return None

    def _get_latest_revision(self, rev_file_path):
        rev_list = self._get_revisions(rev_file_path)
        if not rev_list:
            return None
        return rev_list.latest_revision()

    def _recipe_revisions_file(self, reference):
        recipe_folder = normpath(join(self._store_folder, reference.dir_repr()))
        return join(recipe_folder, REVISIONS_FILE)

    def _package_revisions_file(self, p_reference):
        tmp = normpath(join(self._store_folder, p_reference.conan.dir_repr()))
        revision = {None: ""}.get(p_reference.conan.revision, p_reference.conan.revision)
        p_folder = join(tmp, revision, PACKAGES_FOLDER, p_reference.package_id)
        return join(p_folder, REVISIONS_FILE)

    def ref_with_rev(self, reference):
        if reference.revision:
            return reference

        latest = self.get_last_revision(reference)
        if not latest:
            raise NotFoundException("Recipe not found: '%s'" % reference.full_repr())

        return reference.copy_with_rev(latest.revision)

    def get_revision_time(self, reference):
        try:
            rev_list = self._load_revision_list(reference)
        except IOError:
            return None
        return rev_list.get_time(reference.revision)

    def get_package_revision_time(self, pref):
        try:
            rev_list = self._load_package_revision_list(pref)
        except FileNotFoundError:
            return None

        return rev_list.get_time(pref.revision)

    def p_ref_with_rev(self, p_reference):
        if p_reference.revision and p_reference.conan.revision:
            return p_reference

        if not p_reference.conan.revision:
            # Search the latest recipe revision with the requested package
            p_reference = self.get_latest_package_reference(p_reference)
            return p_reference

        reference = self.ref_with_rev(p_reference.conan)
        ret = PackageReference(reference, p_reference.package_id)

        latest_p = self.get_last_package_revision(ret)
        if not latest_p:
            raise NotFoundException("Package not found: '%s'" % str(p_reference))

        return ret.copy_with_revs(reference.revision, latest_p.revision)

    def _remove_revision_from_index(self, reference):
        rev_list = self._load_revision_list(reference)
        rev_list.remove_revision(reference.revision)
        self._save_revision_list(rev_list, reference)

    def _remove_package_revision_from_index(self, p_reference):
        rev_list = self._load_package_revision_list(p_reference)
        rev_list.remove_revision(p_reference.revision)
        self._save_package_revision_list(rev_list, p_reference)

    def _load_revision_list(self, reference):
        path = self._recipe_revisions_file(reference)
        rev_file = self._storage_adapter.read_file(path, lock_file=path + ".lock")
        return RevisionList.loads(rev_file)

    def _save_revision_list(self, rev_list, reference):
        path = self._recipe_revisions_file(reference)
        self._storage_adapter.write_file(path, rev_list.dumps(), lock_file=path + ".lock")

    def _save_package_revision_list(self, rev_list, p_reference):
        path = self._package_revisions_file(p_reference)
        self._storage_adapter.write_file(path, rev_list.dumps(), lock_file=path + ".lock")

    def _load_package_revision_list(self, pref):
        path = self._package_revisions_file(pref)
        rev_file = self._storage_adapter.read_file(path, lock_file=path + ".lock")
        return RevisionList.loads(rev_file)
