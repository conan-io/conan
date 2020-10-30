import os

from conans.errors import ConanException, ConanMigrationError
from conans.model.version import Version
from conans.util.files import load, save

CONAN_VERSION = "version.txt"


class Migrator(object):

    def __init__(self, conf_path, current_version, out):
        self.conf_path = conf_path

        self.current_version = current_version
        self.file_version_path = os.path.join(self.conf_path, CONAN_VERSION)
        self.out = out

    def migrate(self):
        try:
            old_version = self._load_old_version()
            if old_version != self.current_version:
                self._make_migrations(old_version)
                self._update_version_file()
        except Exception as e:
            self.out.error(str(e))
            raise ConanMigrationError(e)

    def _make_migrations(self, old_version):
        raise NotImplementedError("Implement in subclass")

    def _update_version_file(self):
        try:
            save(self.file_version_path, str(self.current_version))
        except Exception as error:
            raise ConanException("Can't write version file in '{}': {}"
                                 .format(self.file_version_path, str(error)))

    def _load_old_version(self):
        try:
            tmp = load(self.file_version_path)
            old_version = Version(tmp)
        except Exception:
            old_version = None
        return old_version
