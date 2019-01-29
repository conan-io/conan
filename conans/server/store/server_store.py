import os
from os.path import join, normpath, relpath

from conans import DEFAULT_REVISION_V1
from conans.errors import ConanException, NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_FOLDER, PACKAGES_FOLDER
from conans.paths.simple_paths import SimplePaths
from conans.server.revision_list import RevisionList

REVISIONS_FILE = "revisions.txt"


class ServerStore(SimplePaths):

    def __init__(self, storage_adapter):
        super(ServerStore, self).__init__(storage_adapter.base_storage_folder())
        self._storage_adapter = storage_adapter

    def conan(self, ref, resolve_latest=True):
        ref = self.ref_with_rev(ref) if resolve_latest else ref
        tmp = normpath(join(self.store, ref.dir_repr()))
        return join(tmp, ref.revision) if ref.revision else tmp

    def packages(self, ref):
        ref = self.ref_with_rev(ref)
        return join(self.conan(ref), PACKAGES_FOLDER)

    def package(self, pref, short_paths=None):
        pref = self.p_ref_with_rev(pref)
        tmp = join(self.packages(pref.ref), pref.id)
        return join(tmp, pref.revision) if pref.revision else tmp

    def export(self, ref):
        return join(self.conan(ref), EXPORT_FOLDER)

    def get_conanfile_file_path(self, ref, filename):
        ref = self.ref_with_rev(ref)
        abspath = join(self.export(ref), filename)
        return abspath

    def get_package_file_path(self, pref, filename):
        pref = self.p_ref_with_rev(pref)
        p_path = self.package(pref)
        abspath = join(p_path, filename)
        return abspath

    def path_exists(self, path):
        return self._storage_adapter.path_exists(path)

    # ############ SNAPSHOTS (APIv1)
    def get_recipe_snapshot(self, ref):
        """Returns a {filepath: md5} """
        assert isinstance(ref, ConanFileReference)
        return self._get_snapshot_of_files(self.export(ref))

    def get_package_snapshot(self, pref):
        """Returns a {filepath: md5} """
        assert isinstance(pref, PackageReference)
        pref = self.p_ref_with_rev(pref)
        path = self.package(pref)
        return self._get_snapshot_of_files(path)

    def _get_snapshot_of_files(self, relative_path):
        snapshot = self._storage_adapter.get_snapshot(relative_path)
        snapshot = self._relativize_keys(snapshot, relative_path)
        return snapshot

    # ############ ONLY FILE LIST SNAPSHOTS (APIv2)
    def get_recipe_file_list(self, ref):
        """Returns a {filepath: md5} """
        assert isinstance(ref, ConanFileReference)
        return self._get_file_list(self.export(ref))

    def get_package_file_list(self, pref):
        """Returns a {filepath: md5} """
        assert isinstance(pref, PackageReference)
        return self._get_file_list(self.package(pref))

    def _get_file_list(self, relative_path):
        file_list = self._storage_adapter.get_file_list(relative_path)
        file_list = [relpath(old_key, relative_path) for old_key in file_list]
        return file_list

    # ######### DELETE (APIv1 and APIv2)
    def remove_conanfile(self, ref):
        assert isinstance(ref, ConanFileReference)
        result = self._storage_adapter.delete_folder(self.conan(ref, resolve_latest=False))
        if ref.revision:
            self._remove_revision_from_index(ref)
        self._storage_adapter.delete_empty_dirs([ref])
        return result

    def remove_packages(self, ref, package_ids_filter):
        assert isinstance(ref, ConanFileReference)
        assert isinstance(package_ids_filter, list)

        if not package_ids_filter:  # Remove all packages
            packages_folder = self.packages(ref)
            self._storage_adapter.delete_folder(packages_folder)
        else:
            for package_id in package_ids_filter:
                pref = PackageReference(ref, package_id)
                package_folder = self.package(pref)
                self._storage_adapter.delete_folder(package_folder)
        self._storage_adapter.delete_empty_dirs([ref])

    def remove_package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.revision is not None
        assert pref.ref.revision is not None
        package_folder = self.package(pref)
        self._storage_adapter.delete_folder(package_folder)
        self._remove_package_revision_from_index(pref)

    def remove_all_packages(self, ref):
        assert ref.revision is not None
        assert isinstance(ref, ConanFileReference)
        packages_folder = self.packages(ref)
        self._storage_adapter.delete_folder(packages_folder)

    def remove_conanfile_files(self, ref, files):
        subpath = self.export(ref)
        for filepath in files:
            path = join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    def remove_package_files(self, pref, files):
        subpath = self.package(pref)
        for filepath in files:
            path = join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    # ONLY APIv1 URLS
    # ############ DOWNLOAD URLS
    def get_download_conanfile_urls(self, ref, files_subset=None, user=None):
        """Returns a {filepath: url} """
        assert isinstance(ref, ConanFileReference)
        return self._get_download_urls(self.export(ref), files_subset, user)

    def get_download_package_urls(self, pref, files_subset=None, user=None):
        """Returns a {filepath: url} """
        assert isinstance(pref, PackageReference)
        return self._get_download_urls(self.package(pref), files_subset, user)

    # ############ UPLOAD URLS
    def get_upload_conanfile_urls(self, ref, filesizes, user):
        """
        :param ref: ConanFileReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(ref, ConanFileReference)
        assert isinstance(filesizes, dict)
        return self._get_upload_urls(self.export(ref), filesizes, user)

    def get_upload_package_urls(self, pref, filesizes, user):
        """
        :param pref: PackageReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(pref, PackageReference)
        assert isinstance(filesizes, dict)

        return self._get_upload_urls(self.package(pref), filesizes, user)

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
    def get_last_revision(self, ref):
        assert(isinstance(ref, ConanFileReference))
        rev_file_path = self._recipe_revisions_file(ref)
        return self._get_latest_revision(rev_file_path)

    def get_recipe_revisions(self, ref):
        rev_file_path = self._recipe_revisions_file(ref)
        return [ref.copy_with_rev(rev.revision)
                for rev in self._get_revisions(rev_file_path).items()]

    def get_latest_package_reference(self, pref):
        assert(isinstance(pref, PackageReference))
        rev_file_path = self._recipe_revisions_file(pref.ref)
        revs = self._get_revisions(rev_file_path)
        if not revs:
            raise NotFoundException("Recipe not found: '%s'" % str(pref.ref))

        for rev in revs.items():
            pref = PackageReference(pref.ref.copy_with_rev(rev.revision), pref.id)
            tmp = self.get_last_package_revision(pref)
            if tmp:
                pref = pref.copy_with_revs(rev.revision, tmp.revision)
            try:
                folder = self.package(pref)
                if self._storage_adapter.path_exists(folder):
                    return pref
            except NotFoundException:
                pass
        raise NotFoundException("Package not found: '%s'" % str(pref))

    def get_last_package_revision(self, pref):
        assert(isinstance(pref, PackageReference))
        rev_file_path = self._package_revisions_file(pref)
        return self._get_latest_revision(rev_file_path)

    def update_last_revision(self, ref):
        assert(isinstance(ref, ConanFileReference))
        rev_file_path = self._recipe_revisions_file(ref)
        self._update_last_revision(rev_file_path, ref)

    def update_last_package_revision(self, pref):
        assert(isinstance(pref, PackageReference))
        rev_file_path = self._package_revisions_file(pref)
        self._update_last_revision(rev_file_path, pref)

    def _update_last_revision(self, rev_file_path, ref):
        if self._storage_adapter.path_exists(rev_file_path):
            rev_file = self._storage_adapter.read_file(rev_file_path,
                                                       lock_file=rev_file_path + ".lock")
            rev_list = RevisionList.loads(rev_file)
        else:
            rev_list = RevisionList()
        if ref.revision is None:
            raise ConanException("Invalid revision for: %s" % ref.full_repr())
        rev_list.add_revision(ref.revision)
        self._storage_adapter.write_file(rev_file_path, rev_list.dumps(),
                                         lock_file=rev_file_path + ".lock")

    def get_package_revisions(self, pref):
        assert pref.ref.revision is not None
        tmp = self._package_revisions_file(pref)
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
            # FIXING BREAK MIGRATION NOT CREATING INDEXES
            # BOTH FOR RREV AND PREV THE FILE SHOULD BE CREATED WITH "0" REVISION
            if self.path_exists(os.path.join(os.path.dirname(rev_file_path), DEFAULT_REVISION_V1)):
                rev_list = RevisionList()
                rev_list.add_revision(DEFAULT_REVISION_V1)
                self._storage_adapter.write_file(rev_file_path, rev_list.dumps(),
                                                 lock_file=rev_file_path + ".lock")
                return rev_list.latest_revision()
            else:
                return None
        return rev_list.latest_revision()

    def _recipe_revisions_file(self, ref):
        recipe_folder = normpath(join(self._store_folder, ref.dir_repr()))
        return join(recipe_folder, REVISIONS_FILE)

    def _package_revisions_file(self, pref):
        tmp = normpath(join(self._store_folder, pref.ref.dir_repr()))
        revision = {None: ""}.get(pref.ref.revision, pref.ref.revision)
        p_folder = join(tmp, revision, PACKAGES_FOLDER, pref.id)
        return join(p_folder, REVISIONS_FILE)

    def ref_with_rev(self, ref):
        if ref.revision:
            return ref

        latest = self.get_last_revision(ref)
        if not latest:
            raise NotFoundException("Recipe not found: '%s'" % ref.full_repr())

        return ref.copy_with_rev(latest.revision)

    def get_revision_time(self, ref):
        try:
            rev_list = self._load_revision_list(ref)
        except IOError:
            return None
        return rev_list.get_time(ref.revision)

    def get_package_revision_time(self, pref):
        try:
            rev_list = self._load_package_revision_list(pref)
        except (IOError, OSError):
            return None

        return rev_list.get_time(pref.revision)

    def p_ref_with_rev(self, pref):
        if pref.revision and pref.ref.revision:
            return pref

        if not pref.ref.revision:
            # Search the latest recipe revision with the requested package
            pref = self.get_latest_package_reference(pref)
            return pref

        ref = self.ref_with_rev(pref.ref)
        ret = PackageReference(ref, pref.id)

        latest_p = self.get_last_package_revision(ret)
        if not latest_p:
            raise NotFoundException("Package not found: '%s'" % str(pref))

        return ret.copy_with_revs(ref.revision, latest_p.revision)

    def _remove_revision_from_index(self, ref):
        rev_list = self._load_revision_list(ref)
        rev_list.remove_revision(ref.revision)
        self._save_revision_list(rev_list, ref)

    def _remove_package_revision_from_index(self, pref):
        rev_list = self._load_package_revision_list(pref)
        rev_list.remove_revision(pref.revision)
        self._save_package_revision_list(rev_list, pref)

    def _load_revision_list(self, ref):
        path = self._recipe_revisions_file(ref)
        rev_file = self._storage_adapter.read_file(path, lock_file=path + ".lock")
        return RevisionList.loads(rev_file)

    def _save_revision_list(self, rev_list, ref):
        path = self._recipe_revisions_file(ref)
        self._storage_adapter.write_file(path, rev_list.dumps(), lock_file=path + ".lock")

    def _save_package_revision_list(self, rev_list, pref):
        path = self._package_revisions_file(pref)
        self._storage_adapter.write_file(path, rev_list.dumps(), lock_file=path + ".lock")

    def _load_package_revision_list(self, pref):
        path = self._package_revisions_file(pref)
        rev_file = self._storage_adapter.read_file(path, lock_file=path + ".lock")
        return RevisionList.loads(rev_file)
