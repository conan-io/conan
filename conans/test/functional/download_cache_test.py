import os
import platform
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from conans.client.remote_manager import uncompress_file
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput, GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.env_reader import get_env

os.environ["TESTING_REVISIONS_ENABLED"] = "True"


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False),
                     "set TESTING_REVISIONS_ENABLED=1")
class DownloadCacheTest(unittest.TestCase):

    def test(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . mypkg/0.1@user/testing")
        client.run("upload * --all --confirm")
        cache_folder = temp_folder()
        client.run('config set storage.download_cache="%s"' % cache_folder)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        print client.out
        print cache_folder
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        print client.out

