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

    def get_conanfile_path(self, reference, revision):
        if revision is None:
            revision = ""
        return os.path.abspath(os.path.join(self.conan(reference), revision, EXPORT_FOLDER))

    def get_conanfile_files_list(self, reference, revision):
        abspath = self.get_conanfile_path(reference, revision)
        if not os.path.exists(abspath):
            raise NotFoundException("Not found: %s (rev %s)" % (str(reference), revision))
        paths = relative_dirs(abspath)
        return {filepath: sha1sum(os.path.join(abspath, filepath)) for filepath in paths}

    def get_conanfile_file_path(self, reference, filename, revision):
        abspath = os.path.abspath(os.path.join(self.get_conanfile_path(reference, revision),
                                               filename))
        return abspath

    def get_package_path(self, p_reference, revision):
        if revision is None:
            revision = ""
        return os.path.abspath(os.path.join(self.conan(p_reference.conan), revision,
                                            PACKAGES_FOLDER, p_reference.package_id))

    def get_package_files_list(self, p_reference, revision):
        abspath = self.get_package_path(p_reference, revision)
        if not os.path.exists(abspath):
            raise NotFoundException("%s" % str(p_reference))
        paths = relative_dirs(abspath)
        return {filepath: sha1sum(os.path.join(abspath, filepath)) for filepath in paths}

    def get_package_file_path(self, p_reference, filename, revision):
        abspath = os.path.abspath(os.path.join(self.get_package_path(p_reference, revision),
                                               filename))
        return abspath
