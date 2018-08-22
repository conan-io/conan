from os.path import normpath, join

from conans.errors import NotFoundException, ConanException
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import  PACKAGES_FOLDER
from conans.server.revision_list import RevisionList
from conans.server.store.server_store import ServerStore

REVISIONS_FILE = "revisions.txt"


class ServerStoreRevisions(ServerStore):

    def __init__(self, storage_adapter):
        super(ServerStoreRevisions, self).__init__(storage_adapter)

    # Methods to override some basics from paths to allow revisions paths (reading latest)
    def conan(self, reference, resolve_latest=True):
        reference = self.ref_with_rev(reference) if resolve_latest else reference
        tmp = super(ServerStoreRevisions, self).conan(reference)
        return join(tmp, reference.revision) if reference.revision else tmp

    def packages(self, reference):
        reference = self.ref_with_rev(reference)
        return super(ServerStoreRevisions, self).packages(reference)

    def package(self, p_reference, short_paths=None):
        p_reference = self._p_ref_with_rev(p_reference)
        tmp = super(ServerStoreRevisions, self).package(p_reference, short_paths)
        return join(tmp, p_reference.revision) if p_reference.revision else tmp

    def get_conanfile_file_path(self, reference, filename):
        reference = self.ref_with_rev(reference)
        return super(ServerStoreRevisions, self).get_conanfile_file_path(reference, filename)

    def get_package_file_path(self, p_reference, filename):
        p_reference = self._p_ref_with_rev(p_reference)
        return super(ServerStoreRevisions, self).get_package_file_path(p_reference, filename)

    def get_package_snapshot(self, p_reference):
        """Returns a {filepath: md5} """
        p_reference = self._p_ref_with_rev(p_reference)
        return super(ServerStoreRevisions, self).get_package_snapshot(p_reference)

    # Methods to manage revisions
    def get_last_revision(self, reference):
        assert(isinstance(reference, ConanFileReference))
        rev_file_path = self._recipe_revisions_file(reference)
        return self._get_latest_revision(rev_file_path)

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
        if not reference.revision:
            raise ConanException("Invalid revision for: %s" % reference.full_repr())
        rev_list.add_revision(reference.revision)
        self._storage_adapter.write_file(rev_file_path, rev_list.dumps(),
                                         lock_file=rev_file_path + ".lock")

    def _get_latest_revision(self, rev_file_path):
        if self._storage_adapter.path_exists(rev_file_path):
            rev_file = self._storage_adapter.read_file(rev_file_path,
                                                       lock_file=rev_file_path + ".lock")
            rev_list = RevisionList.loads(rev_file)
            return rev_list.latest_revision()
        else:
            return None

    def _recipe_revisions_file(self, reference):
        recipe_folder = normpath(join(self._store_folder, "/".join(reference)))
        return join(recipe_folder, REVISIONS_FILE)

    def _package_revisions_file(self, p_reference):
        tmp = normpath(join(self._store_folder, "/".join(p_reference.conan)))
        revision = {None: ""}.get(p_reference.conan.revision, p_reference.conan.revision)
        p_folder = join(tmp, revision, PACKAGES_FOLDER, p_reference.package_id)
        return join(p_folder, REVISIONS_FILE)

    def ref_with_rev(self, reference):
        if reference.revision:
            return reference

        latest = self.get_last_revision(reference)
        if not latest:
            raise NotFoundException("Recipe not found: '%s'" % reference.full_repr())

        return reference.copy_with_revision(latest)

    def _p_ref_with_rev(self, p_reference):
        if p_reference.revision:
            return p_reference

        reference = self.ref_with_rev(p_reference.conan)
        ret = PackageReference(reference, p_reference.package_id)

        latest = self.get_last_package_revision(ret)
        if not latest:
            raise NotFoundException("Package not found: '%s'" % str(p_reference))

        return ret.copy_with_revisions(reference.revision, latest)

    def _remove_revision(self, rev_file_path, revision):
        rev_file = self._storage_adapter.read_file(rev_file_path,
                                                   lock_file=rev_file_path + ".lock")
        rev_list = RevisionList.loads(rev_file)
        rev_list.remove_revision(revision)
        self._storage_adapter.write_file(rev_file_path, rev_list.dumps(),
                                         lock_file=rev_file_path + ".lock")

    def remove_conanfile(self, reference):
        assert isinstance(reference, ConanFileReference)
        result = self._storage_adapter.delete_folder(self.conan(reference, resolve_latest=False))
        if reference.revision:
            rev_file_path = self._recipe_revisions_file(reference)
            self._remove_revision(rev_file_path, reference.revision)
        self._storage_adapter.delete_empty_dirs([reference])
        return result
