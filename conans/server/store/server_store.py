import os

import fasteners

from conans.errors import NotFoundException
from conans.paths import SimplePaths, EXPORT_FOLDER, PACKAGES_FOLDER
from conans.util.files import relative_dirs, sha1sum
from conans.util.log import logger

LAST_REVISION_FILE = "last_revision_file.txt"


class ServerStore(SimplePaths):
    """Class to manage the disk store directly and without abstract classes
    nor more complications"""

    def __init__(self, storage_path):
        super(ServerStore, self).__init__(storage_path)

    def _last_revision_path(self, reference):
        return os.path.join(self.conan(reference), LAST_REVISION_FILE)

    def _last_package_revision_path(self, revision, p_reference):
        p_folder = os.path.abspath(os.path.join(self.conan(p_reference.conan), revision,
                                                PACKAGES_FOLDER, p_reference.package_id))
        return os.path.join(p_folder, LAST_REVISION_FILE)

    def get_last_revision(self, reference):
        rev_file = self._last_revision_path(reference)
        if os.path.exists(rev_file):
            with open(rev_file, "r") as file:
                return file.read()
        else:
            return None

    def update_last_revision(self, reference, revision):
        rev_file = self._last_revision_path(reference)
        with fasteners.InterProcessLock(rev_file + ".lock", logger=logger):
            with open(rev_file, "w") as f:
                f.write(revision)

    def get_last_package_revision(self, revision, p_reference):
        rev_file = self._last_package_revision_path(revision, p_reference)
        if os.path.exists(rev_file):
            with open(rev_file, "r") as file:
                return file.read()
        else:
            return None

    def update_last_package_revision(self, p_reference, revision):
        rev_file = self._last_package_revision_path(p_reference)
        with fasteners.InterProcessLock(rev_file + ".lock", logger=logger):
            with open(rev_file, "w") as f:
                f.write(revision)

    def get_conanfile_path(self, reference):
        revision = {None: ""}.get(reference.revision, reference.revision)
        return os.path.abspath(os.path.join(self.conan(reference), revision, EXPORT_FOLDER))

    def get_conanfile_files_list(self, reference):
        abspath = self.get_conanfile_path(reference)
        if not os.path.exists(abspath):
            raise NotFoundException("Not found: %s (rev %s)" % (str(reference), reference.revision))
        paths = relative_dirs(abspath)
        return {filepath: sha1sum(os.path.join(abspath, filepath)) for filepath in paths}

    def get_conanfile_file_path(self, reference, filename):
        abspath = os.path.abspath(os.path.join(self.get_conanfile_path(reference), filename))
        return abspath

    def get_package_path(self, p_reference):
        revision = {None: ""}.get(p_reference.conan.revision, p_reference.conan.revision)
        p_revision = {None: ""}.get(p_reference.revision, p_reference.revision)
        return os.path.abspath(os.path.join(self.conan(p_reference.conan), revision,
                                            PACKAGES_FOLDER, p_reference.package_id, p_revision))

    def get_package_files_list(self, p_reference):
        abspath = self.get_package_path(p_reference)
        if not os.path.exists(abspath):
            raise NotFoundException("%s" % str(p_reference))
        paths = relative_dirs(abspath)
        return {filepath: sha1sum(os.path.join(abspath, filepath)) for filepath in paths}

    def get_package_file_path(self, p_reference, filename):
        p_path = self.get_package_path(p_reference)
        abspath = os.path.abspath(os.path.join(p_path, filename))
        return abspath
