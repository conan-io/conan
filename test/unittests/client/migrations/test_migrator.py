import os
import platform

import pytest

from conans.errors import ConanMigrationError
from conans.migrations import Migrator
from conan.test.utils.test_files import temp_folder


class FakeMigrator(Migrator):

    def __init__(self, cache_folder, current_version):
        self.cache_folder = cache_folder
        super(FakeMigrator, self).__init__(cache_folder, current_version)


class TestMigratorPermissionTest:

    @pytest.mark.skipif(platform.system() == "Windows", reason="Can't apply chmod on Windows")
    def test_invalid_permission(self):
        conf_path = temp_folder(False)
        os.chmod(conf_path, 0o444)
        conf_path = os.path.join(conf_path, "foo")
        migrator = FakeMigrator(conf_path, "latest")
        with pytest.raises(ConanMigrationError) as error:
            migrator.migrate()
        assert f"Can't write version file in '{conf_path}/version.txt'" in str(error.value)
