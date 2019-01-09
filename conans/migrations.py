import os

from conans.errors import ConanException
from conans.model.version import Version
from conans.util.files import load, save

CONAN_VERSION = "version.txt"


class Migrator(object):

    def __init__(self, conf_path, store_path, current_version, out):
        self.conf_path = conf_path
        self.store_path = store_path

        self.current_version = current_version
        self.file_version_path = os.path.join(self.conf_path, CONAN_VERSION)
        self.out = out

    def migrate(self):
        old_version = self._load_old_version()
        if old_version != self.current_version:
            self._make_migrations(old_version)
            self._update_version_file()

    def _make_migrations(self, old_version):
        raise NotImplementedError("Implement in subclass")

    def _update_version_file(self):
        try:
            save(self.file_version_path, str(self.current_version))
        except Exception:
            raise ConanException("Can't write version file in %s" % self.file_version_path)

    def _load_old_version(self):
        try:
            tmp = load(self.file_version_path)
            old_version = Version(tmp)
        except:
            old_version = None
        return old_version
