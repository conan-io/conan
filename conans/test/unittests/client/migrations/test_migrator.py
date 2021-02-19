# coding=utf-8

import unittest
import os
import platform

import pytest

from conans.migrations import Migrator
from conans.test.utils.mocks import TestBufferConanOutput
from conans.test.utils.test_files import temp_folder
from conans.errors import ConanMigrationError


class FakeMigrator(Migrator):

    def __init__(self, cache_folder, current_version, out):
        self.cache_folder = cache_folder
        super(FakeMigrator, self).__init__(cache_folder, current_version, out)

    def _make_migrations(self, old_version):
        pass


class MigratorPermissionTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() == "Windows", reason="Can't apply chmod on Windows")
    def test_invalid_permission(self):
        out = TestBufferConanOutput()
        conf_path = temp_folder(False)
        os.chmod(conf_path, 0o444)
        conf_path = os.path.join(conf_path, "foo")
        migrator = FakeMigrator(conf_path, "latest", out)
        with self.assertRaises(ConanMigrationError) as error:
            migrator.migrate()
        self.assertEqual("Can't write version file in '{0}/version.txt': The folder {0} does not "
                         "exist and could not be created (Permission denied).".format(conf_path),
                         str(error.exception))
