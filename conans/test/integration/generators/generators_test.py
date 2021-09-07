import os
import re
import unittest


import pytest

from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID
from conans.model.graph_lock import LOCKFILE
from conans.test.utils.tools import TestClient


class GeneratorsTest(unittest.TestCase):

    def test_error(self):
        base = '''
[generators]
unknown
'''
        client = TestClient()
        client.save({"conanfile.txt": base})
        client.run("install . --build", assert_error=True)
        self.assertIn("ERROR: Invalid generator 'unknown'. Available types:", client.out)

    def test_base(self):
        base = '''
[generators]
cmake
ycm
    '''
        files = {"conanfile.txt": base}
        client = TestClient()
        client.save(files)
        client.run("install . --build")

        self.assertEqual(sorted(['conanfile.txt', 'conanbuildinfo.cmake',
                                 'conan_ycm_flags.json', 'conan_ycm_extra_conf.py']),
                         sorted(os.listdir(client.current_folder)))

    @pytest.mark.xfail(reason="Generator qmake generator to be revisited")
    def test_srcdirs(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
from conans.tools import save
import os
class TestConan(ConanFile):
    def package(self):
        save(os.path.join(self.package_folder, "src/file.h"), "//header")
    def package_info(self):
        self.cpp_info.srcdirs = ["src"]
"""

        client.save({"conanfile.py": conanfile})
        client.run("create . mysrc/0.1@user/testing")
        client.run("install mysrc/0.1@user/testing -g cmake")

        cmake = client.load("conanbuildinfo.cmake")
        src_dirs = re.search('set\(CONAN_SRC_DIRS_MYSRC "(.*)"\)', cmake).group(1)
        self.assertIn("mysrc/0.1/user/testing/package/%s/src" % NO_SETTINGS_PACKAGE_ID,
                      src_dirs)
