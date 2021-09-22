# coding=utf-8

import os
import platform
import unittest

import pytest

from conans.cli.output import ConanOutput
from conans.errors import ConanMigrationError
from conans.migrations import Migrator
from conans.test.utils.test_files import temp_folder


class FakeMigrator(Migrator):

    def __init__(self, cache_folder, current_version):
        self.cache_folder = cache_folder
        super(FakeMigrator, self).__init__(cache_folder, current_version)


class MigratorPermissionTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() == "Windows", reason="Can't apply chmod on Windows")
    def test_invalid_permission(self):
        conf_path = temp_folder(False)
        os.chmod(conf_path, 0o444)
        conf_path = os.path.join(conf_path, "foo")
        migrator = FakeMigrator(conf_path, "latest")
        with self.assertRaises(ConanMigrationError) as error:
            migrator.migrate()
        self.assertEqual("Can't write version file in '{0}/version.txt': The folder {0} does not "
                         "exist and could not be created (Permission denied).".format(conf_path),
                         str(error.exception))
