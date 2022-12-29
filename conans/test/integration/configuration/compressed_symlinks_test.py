import os
import platform
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.paths import PACKAGE_TGZ_NAME
from conans.test.utils.tools import TestServer, TurboTestClient


class CompressSymlinksZeroSize(unittest.TestCase):

    @pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
    def test_package_symlinks_zero_size(self):
        server = TestServer()
        client = TurboTestClient(servers={"default": server})

        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):

    def package(self):
        # Link to file.txt and then remove it
        tools.save(os.path.join(self.package_folder, "file.txt"), "contents")
        os.symlink("file.txt", os.path.join(self.package_folder, "link.txt"))
"""
        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        # By default it is not allowed
        pref = client.create(ref, conanfile=conanfile)
        # Upload, it will create the tgz
        client.upload_all(ref)

        # We can uncompress it without warns
        p_folder = client.cache.package_layout(pref.ref).download_package(pref)
        tgz = os.path.join(p_folder, PACKAGE_TGZ_NAME)
        client.run_command('gzip -d "{}"'.format(tgz))
        client.run_command('tar tvf "{}"'.format(os.path.join(p_folder, "conan_package.tar")))
        lines = str(client.out).splitlines()
        """
-rw-r--r-- 0/0               8 1970-01-01 01:00 file.txt
lrw-r--r-- 0/0               0 1970-01-01 01:00 link.txt -> file.txt
        """

        self.assertIn("link.txt", " ".join(lines))
        for line in lines:
            if ".txt" not in line:
                continue

            size = int([i for i in line.split(" ") if i][2])
            if "link.txt" in line:
                self.assertEqual(int(size), 0)
            elif "file.txt":
                self.assertGreater(int(size), 0)
