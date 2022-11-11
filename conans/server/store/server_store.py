import os
from os.path import join, normpath, relpath

from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.server.revision_list import RevisionList

REVISIONS_FILE = "revisions.txt"
SERVER_EXPORT_FOLDER = "export"
SERVER_PACKAGES_FOLDER = "package"


def ref_dir_repr(ref):
    return "/".join([ref.name, str(ref.version), ref.user or "_", ref.channel or "_"])


class ServerStore(object):

    def __init__(self, storage_adapter):
        self._storage_adapter = storage_adapter
        self._store_folder = storage_adapter._store_folder

    @property
    def store(self):
        return self._store_folder

    def base_folder(self, ref):
        assert ref.revision is not None, "BUG: server store needs RREV to get recipe reference"
        tmp = normpath(join(self.store, ref_dir_repr(ref)))
        return join(tmp, ref.revision)

    def conan_revisions_root(self, ref):
        """Parent folder of the conan package, for all the revisions"""
        assert not ref.revision, "BUG: server store doesn't need RREV to conan_revisions_root"
        return normpath(join(self.store, ref_dir_repr(ref)))

    def packages(self, ref):
        return join(self.base_folder(ref), SERVER_PACKAGES_FOLDER)

    def package_revisions_root(self, pref):
        assert pref.revision is None, "BUG: server store doesn't need PREV to " \
                                      "package_revisions_root"
        assert pref.ref.revision is not None, "BUG: server store needs RREV to " \
                                              "package_revisions_root"
        tmp = join(self.packages(pref.ref), pref.package_id)
        return tmp

    def package(self, pref):
        assert pref.revision is not None, "BUG: server store needs PREV for package"
        tmp = join(self.packages(pref.ref), pref.package_id)
        return join(tmp, pref.revision)

    def export(self, ref):
        return join(self.base_folder(ref), SERVER_EXPORT_FOLDER)

    def get_recipe_file_path(self, ref, filename):
        abspath = join(self.export(ref), filename)
        return abspath

    def get_package_file_path(self, pref, filename):
        p_path = self.package(pref)
        abspath = join(p_path, filename)
        return abspath

    def path_exists(self, path):
        return self._storage_adapter.path_exists(path)

    # ############ ONLY FILE LIST SNAPSHOTS (APIv2)
    def get_recipe_file_list(self, ref):
        """Returns a  [filepath] """
        assert isinstance(ref, RecipeReference)
        return self._get_file_list(self.export(ref))

    def get_package_file_list(self, pref):
        """Returns a  [filepath] """
        assert isinstance(pref, PkgReference)
        return self._get_file_list(self.package(pref))

    def _get_file_list(self, relative_path):
        file_list = self._storage_adapter.get_file_list(relative_path)
        file_list = [relpath(old_key, relative_path) for old_key in file_list]
        return file_list

    def _delete_empty_dirs(self, ref):
        lock_files = {REVISIONS_FILE, "%s.lock" % REVISIONS_FILE}

        ref_path = normpath(join(self.store, ref_dir_repr(ref)))
        if ref.revision:
            ref_path = join(ref_path, ref.revision)
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

    # ######### DELETE (APIv1 and APIv2)
    def remove_recipe(self, ref):
        assert isinstance(ref, RecipeReference)
        if not ref.revision:
            self._storage_adapter.delete_folder(self.conan_revisions_root(ref))
        else:
            self._storage_adapter.delete_folder(self.base_folder(ref))
            self._remove_revision_from_index(ref)
        self._delete_empty_dirs(ref)

    def remove_packages(self, ref, package_ids_filter):
        assert isinstance(ref, RecipeReference)
        assert isinstance(package_ids_filter, list)

        if not package_ids_filter:  # Remove all packages
            packages_folder = self.packages(ref)
            self._storage_adapter.delete_folder(packages_folder)
        else:
            for package_id in package_ids_filter:
                pref = PkgReference(ref, package_id)
                # Remove all package revisions
                package_folder = self.package_revisions_root(pref)
                self._storage_adapter.delete_folder(package_folder)
        self._delete_empty_dirs(ref)

    def remove_package(self, pref):
        assert isinstance(pref, PkgReference)
        assert pref.revision is not None, "BUG: server store needs PREV remove_package"
        assert pref.ref.revision is not None, "BUG: server store needs RREV remove_package"
        package_folder = self.package(pref)
        self._storage_adapter.delete_folder(package_folder)
        self._remove_package_revision_from_index(pref)

    def remove_all_packages(self, ref):
        assert ref.revision is not None, "BUG: server store needs RREV remove_all_packages"
        assert isinstance(ref, RecipeReference)
        packages_folder = self.packages(ref)
        self._storage_adapter.delete_folder(packages_folder)

    def remove_recipe_files(self, ref, files):
        subpath = self.export(ref)
        for filepath in files:
            path = join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    def remove_package_files(self, pref, files):
        subpath = self.package(pref)
        for filepath in files:
            path = join(subpath, filepath)
            self._storage_adapter.delete_file(path)

    def get_upload_package_urls(self, pref, filesizes, user):
        """
        :param pref: PkgReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        assert isinstance(pref, PkgReference)
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
        assert(isinstance(ref, RecipeReference))
        rev_file_path = self._recipe_revisions_file(ref)
        return self._get_latest_revision(rev_file_path)

    def get_recipe_revisions_references(self, ref):
        """Returns a RevisionList"""
        if ref.revision:
            tmp = RevisionList()
            tmp.add_revision(ref.revision)
            return tmp.as_list()
        rev_file_path = self._recipe_revisions_file(ref)
        revs = self._get_revisions_list(rev_file_path).as_list()
        if not revs:
            raise RecipeNotFoundException(ref)
        return revs

    def get_last_package_revision(self, pref):
        assert(isinstance(pref, PkgReference))
        rev_file_path = self._package_revisions_file(pref)
        rev = self._get_latest_revision(rev_file_path)
        if rev:
            return PkgReference(pref.ref, pref.package_id, rev.revision, rev.time)
        return None

    def update_last_revision(self, ref):
        assert(isinstance(ref, RecipeReference))
        rev_file_path = self._recipe_revisions_file(ref)
        self._update_last_revision(rev_file_path, ref)

    def update_last_package_revision(self, pref):
        assert(isinstance(pref, PkgReference))
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
            raise ConanException("Invalid revision for: %s" % repr(ref))
        rev_list.add_revision(ref.revision)
        self._storage_adapter.write_file(rev_file_path, rev_list.dumps(),
                                         lock_file=rev_file_path + ".lock")

    def get_package_revisions_references(self, pref):
        """Returns a RevisionList"""
        assert pref.ref.revision is not None, \
            "BUG: server store needs PREV get_package_revisions_references"
        if pref.revision:
            tmp = RevisionList()
            tmp.add_revision(pref.revision)
            return [PkgReference(pref.ref, pref.package_id, rev.revision, rev.time)
                    for rev in tmp.as_list()]

        tmp = self._package_revisions_file(pref)
        ret = self._get_revisions_list(tmp).as_list()
        if not ret:
            raise PackageNotFoundException(pref)
        return [PkgReference(pref.ref, pref.package_id, rev.revision, rev.time) for rev in ret]

    def _get_revisions_list(self, rev_file_path):
        if self._storage_adapter.path_exists(rev_file_path):
            rev_file = self._storage_adapter.read_file(rev_file_path,
                                                       lock_file=rev_file_path + ".lock")
            rev_list = RevisionList.loads(rev_file)
            return rev_list
        else:
            return RevisionList()

    def _get_latest_revision(self, rev_file_path):
        rev_list = self._get_revisions_list(rev_file_path)
        if not rev_list:
            return None
        return rev_list.latest_revision()

    def _recipe_revisions_file(self, ref):
        recipe_folder = normpath(join(self._store_folder, ref_dir_repr(ref)))
        return join(recipe_folder, REVISIONS_FILE)

    def _package_revisions_file(self, pref):
        tmp = normpath(join(self._store_folder, ref_dir_repr(pref.ref)))
        revision = {None: ""}.get(pref.ref.revision, pref.ref.revision)
        p_folder = join(tmp, revision, SERVER_PACKAGES_FOLDER, pref.package_id)
        return join(p_folder, REVISIONS_FILE)

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
