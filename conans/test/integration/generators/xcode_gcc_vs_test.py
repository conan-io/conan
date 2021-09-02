import os
import textwrap
import unittest

import pytest

from conans.model.graph_lock import LOCKFILE
from conans.model.ref import ConanFileReference
from conans.paths import BUILD_INFO_CMAKE, CONANFILE_TXT
from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="Generator cmake to be removed, XCode to be revisited")
class VSXCodeGeneratorsTest(unittest.TestCase):

    def test_generators(self):
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        client = TestClient()
        client.save({"conanfile.py": textwrap.dedent("""
            from conans import ConanFile
            import os
            class Pkg(ConanFile):
                def package(self):
                    os.makedirs(os.path.join(self.package_folder, "lib"))
                    os.makedirs(os.path.join(self.package_folder, "include"))
                def package_info(self):
                    self.cpp_info.libs = ["hello"]
                    self.cpp_info.cxxflags = ["-some_cxx_compiler_flag"]
                    self.cpp_info.cflags = ["-some_c_compiler_flag"]
                    self.cpp_info.system_libs = ["system_lib1"]
            """)})
        client.run("export . Hello/0.1@lasote/stable")
        conanfile_txt = textwrap.dedent('''
            [requires]
            Hello/0.1@lasote/stable # My req comment
            [generators]
            cmake
            ''')
        client.save({"conanfile.txt": conanfile_txt}, clean_first=True)

        # Install requirements
        client.run('install . --build missing')

        current_files = os.listdir(client.current_folder)
        for f in [CONANFILE_TXT, BUILD_INFO_CMAKE, LOCKFILE]:
            assert f in current_files

        cmake = client.load(BUILD_INFO_CMAKE)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("CONAN_LIBS", cmake)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)

        latest_rrev = client.cache.get_latest_rrev(ref)
        pkg_ids = client.cache.get_package_ids(latest_rrev)
        latest_prev = client.cache.get_latest_prev(pkg_ids[0])
        package_path = client.cache.pkg_layout(latest_prev).package().replace("\\", "/")
        self.assertIn(f"{package_path}", cmake)
