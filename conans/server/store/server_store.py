import os
from os.path import normpath

import fasteners

from conans.errors import NotFoundException
from conans.model.ref import PackageReference
from conans.paths import SimplePaths, EXPORT_FOLDER, PACKAGES_FOLDER
from conans.util.files import relative_dirs, sha1sum
from conans.util.log import logger

LAST_REVISION_FILE = "last_rev.txt"


class ServerStore(SimplePaths):
    """Class to manage the disk store directly and without abstract classes
    nor more complications"""

    def __init__(self, storage_path, revisions_enabled):
        super(ServerStore, self).__init__(storage_path)
        self._revisions_enabled = revisions_enabled

    def _last_revision_path(self, reference):
        tmp = normpath(os.path.join(self._store_folder, "/".join(reference)))
        revision = {None: ""}.get(reference.revision, reference.revision)
        recipe_folder = os.path.abspath(os.path.join(tmp, revision))
        return os.path.join(recipe_folder, LAST_REVISION_FILE)

    def _last_package_revision_path(self, p_reference):
        tmp = normpath(os.path.join(self._store_folder, "/".join(p_reference.conan)))
        revision = {None: ""}.get(p_reference.conan.revision, p_reference.conan.revision)
        p_folder = os.path.abspath(os.path.join(tmp, revision, PACKAGES_FOLDER,
                                                p_reference.package_id))
        return os.path.join(p_folder, LAST_REVISION_FILE)

    def conan(self, reference):
        reference = self._patch_ref(reference)
        tmp = normpath(os.path.join(self._store_folder, "/".join(reference)))
        revision = {None: ""}.get(reference.revision, reference.revision)
        return os.path.abspath(os.path.join(tmp, revision))

    def packages(self, reference):
        reference = self._patch_ref(reference)
        return os.path.abspath(os.path.join(self.conan(reference), PACKAGES_FOLDER))

    def package(self, p_reference, short_paths=None):
        p_reference = self._patch_package_ref(p_reference)
        p_revision = {None: ""}.get(p_reference.revision, p_reference.revision)
        return os.path.abspath(os.path.join(self.packages(p_reference.conan),
                                            p_reference.package_id, p_revision))

    def get_last_revision(self, reference):
        rev_file = self._last_revision_path(reference)
        if os.path.exists(rev_file):
            with open(rev_file) as f:
                return f.read()
        else:
            return None

    def update_last_revision(self, reference):
        rev_file = self._last_revision_path(reference)
        with fasteners.InterProcessLock(rev_file + ".lock", logger=logger):
            with open(rev_file, "w") as f:
                f.write(reference.revision)

    def get_last_package_revision(self, p_reference):
        rev_file = self._last_package_revision_path(p_reference)
        if os.path.exists(rev_file):
            with open(rev_file) as f:
                return f.read()
        else:
            return None

    def update_last_package_revision(self, p_reference):
        rev_file = self._last_package_revision_path(p_reference)
        with fasteners.InterProcessLock(rev_file + ".lock", logger=logger):
            with open(rev_file, "w") as f:
                f.write(p_reference.revision)

    def export(self, reference):
        return os.path.abspath(os.path.join(self.conan(reference), EXPORT_FOLDER))

    def get_conanfile_files_list(self, reference):
        reference = self._patch_ref(reference)
        abspath = self.export(reference)
        if not os.path.exists(abspath):
            raise NotFoundException("Not found: %s (rev %s)" % (str(reference), reference.revision))
        paths = relative_dirs(abspath)
        return {filepath: sha1sum(os.path.join(abspath, filepath)) for filepath in paths}

    def get_conanfile_file_path(self, reference, filename):
        reference = self._patch_ref(reference)
        abspath = os.path.abspath(os.path.join(self.export(reference), filename))
        return abspath

    def get_package_files_list(self, p_reference):
        p_reference = self._patch_package_ref(p_reference)
        abspath = self.package(p_reference)
        if not os.path.exists(abspath):
            raise NotFoundException("%s" % str(p_reference))
        paths = relative_dirs(abspath)
        return {filepath: sha1sum(os.path.join(abspath, filepath)) for filepath in paths}

    def get_package_file_path(self, p_reference, filename):
        p_reference = self._patch_package_ref(p_reference)
        p_path = self.package(p_reference)
        abspath = os.path.abspath(os.path.join(p_path, filename))
        return abspath

    def _patch_ref(self, reference):
        if not self._revisions_enabled:
            return reference
        if reference.revision:
            return reference

        latest = self.get_last_revision(reference)
        if not latest:
            raise NotFoundException("Recipe not found: '%s'" % str(reference))

        reference.revision = latest
        return reference

    def _patch_package_ref(self, p_reference):
        if not self._revisions_enabled:
            return p_reference
        if p_reference.revision:
            return p_reference

        latest = self.get_last_package_revision(p_reference)
        if not latest:
            raise NotFoundException("Package not found: '%s'" % str(p_reference))

        reference = self._patch_ref(p_reference.conan)
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
