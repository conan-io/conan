import os
import stat
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="Legacy conan.conf configuration deprecated")
class DeployImportFilePermissionTest(unittest.TestCase):
    # FIXME: CONAN_READ_ONLY to be revisited and reconsidered, depends on "install-folder" idea

    def setUp(self):
        self.file_name = 'myheader.h'

    def _client(self, ro_file, ro_cache):
        client = TestClient()
        if ro_cache:
            conan_conf = textwrap.dedent("""
                                        [general]
                                        read_only_cache=True
                                    """)
            client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        with client.chdir('recipe'):
            conanfile = """from conan import ConanFile
class MyPkg(ConanFile):
    exports_sources = "*.h"
    def package(self):
        self.copy("*.h")

    def deploy(self):
        self.copy("*.h")
"""
            client.save({"conanfile.py": conanfile,
                         self.file_name: "my header"})
            os.chmod(os.path.join(client.current_folder, self.file_name), 0o444 if ro_file else 0o644)
            client.run("create . --name=pkg --version=0.1 --user=lasote --channel=channel")
        return client

    def _import(self, client):
        conanfile = """[requires]
pkg/0.1@lasote/channel

[imports]
., *.h -> .
"""
        client.save({'conanfile.txt': conanfile})
        with client.chdir('import'):
            client.run('install ..')

    def _deploy(self, client):
        with client.chdir('deploy'):
            client.run('install --reference=pkg/0.1@lasote/channel')

    def _is_file_writable(self, client, folder):
        return bool(os.stat(os.path.join(client.current_folder, folder, self.file_name)).st_mode & stat.S_IWRITE)

    def test_import_rw_file_rw_cache(self):
        client = self._client(ro_file=False, ro_cache=False)
        self._import(client)
        self.assertTrue(self._is_file_writable(client, 'import'))

    def test_import_ro_file_rw_cache(self):
        client = self._client(ro_file=True, ro_cache=False)
        self._import(client)
        self.assertFalse(self._is_file_writable(client, 'import'))

    def test_import_rw_file_ro_cache(self):
        client = self._client(ro_file=False, ro_cache=True)
        self._import(client)
        self.assertTrue(self._is_file_writable(client, 'import'))

    def test_import_ro_file_ro_cache(self):
        client = self._client(ro_file=True, ro_cache=True)
        self._import(client)
        self.assertTrue(self._is_file_writable(client, 'import'))

    def test_deploy_rw_file_rw_cache(self):
        client = self._client(ro_file=False, ro_cache=False)
        self._deploy(client)
        self.assertTrue(self._is_file_writable(client, 'deploy'))

    def test_deploy_ro_file_rw_cache(self):
        client = self._client(ro_file=True, ro_cache=False)
        self._deploy(client)
        self.assertFalse(self._is_file_writable(client, 'deploy'))

    def test_deploy_rw_file_ro_cache(self):
        client = self._client(ro_file=False, ro_cache=True)
        self._deploy(client)
        self.assertTrue(self._is_file_writable(client, 'deploy'))

    def test_deploy_ro_file_ro_cache(self):
        client = self._client(ro_file=True, ro_cache=True)
        self._deploy(client)
        self.assertTrue(self._is_file_writable(client, 'deploy'))
