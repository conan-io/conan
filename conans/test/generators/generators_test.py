import os
import platform
import unittest

from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conans.util.files import load
from conans.model.ref import ConanFileReference
import re


class GeneratorsTest(unittest.TestCase):

    def test_error(self):
        base = '''
[generators]
unknown
'''
        client = TestClient()
        client.save({"conanfile.txt": base})
        error = client.run("install . --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Invalid generator 'unknown'. Available types:", client.out)

    def test_base(self):
        base = '''
[generators]
cmake
gcc
qbs
qmake
scons
txt
virtualenv
visual_studio
visual_studio_legacy
xcode
ycm
    '''
        files = {"conanfile.txt": base}
        client = TestClient()
        client.save(files)
        client.run("install . --build")

        venv_files = ["activate.sh", "deactivate.sh"]
        if platform.system() == "Windows":
            venv_files.extend(["activate.bat", "deactivate.bat", "activate.ps1",
                               "deactivate.ps1"])

        self.assertEqual(sorted(['conanfile.txt', 'conaninfo.txt', 'conanbuildinfo.cmake',
                                 'conanbuildinfo.gcc', 'conanbuildinfo.qbs', 'conanbuildinfo.pri',
                                 'SConscript_conan', 'conanbuildinfo.txt', 'conanbuildinfo.props',
                                 'conanbuildinfo.vsprops', 'conanbuildinfo.xcconfig',
                                 'conan_ycm_flags.json', 'conan_ycm_extra_conf.py'] + venv_files),
                         sorted(os.listdir(client.current_folder)))

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

        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        src_dirs = re.search('set\(CONAN_SRC_DIRS_MYSRC "(.*)"\)', cmake).group(1)
        self.assertIn("mysrc/0.1/user/testing/package/%s/src" % NO_SETTINGS_PACKAGE_ID,
                      src_dirs)

    def test_qmake(self):
        client = TestClient()
        dep = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "Pkg"
    version = "0.1"

    def package_info(self):
        self.cpp_info.libs = ["hello"]
        self.cpp_info.debug.includedirs = []
        self.cpp_info.debug.libs = ["hellod"]
        self.cpp_info.release.libs = ["hellor"]

"""
        base = '''
[requires]
Pkg/0.1@lasote/testing
[generators]
qmake
    '''
        client.save({"conanfile.py": dep})
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": base}, clean_first=True)
        client.run("install . --build")

        qmake = load(os.path.join(client.current_folder, "conanbuildinfo.pri"))
        self.assertIn("CONAN_RESDIRS += ", qmake)
        self.assertEqual(qmake.count("CONAN_LIBS += "), 1)
        self.assertIn("CONAN_LIBS_PKG_RELEASE += -lhellor", qmake)
        self.assertIn("CONAN_LIBS_PKG_DEBUG += -lhellod", qmake)
        self.assertIn("CONAN_LIBS_PKG += -lhello", qmake)
        self.assertIn("CONAN_LIBS_RELEASE += -lhellor", qmake)
        self.assertIn("CONAN_LIBS_DEBUG += -lhellod", qmake)
        self.assertIn("CONAN_LIBS += -lhello", qmake)

    def test_qmake_hyphen_dot(self):
        client = TestClient()
        dep = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "Pkg-Name.World"
    version = "0.1"

    def package_info(self):
        self.cpp_info.libs = ["hello"]
        self.cpp_info.debug.includedirs = []
        self.cpp_info.debug.libs = ["hellod"]
        self.cpp_info.release.libs = ["hellor"]

"""
        base = '''
[requires]
Pkg-Name.World/0.1@lasote/testing
[generators]
qmake
    '''
        client.save({"conanfile.py": dep})
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": base}, clean_first=True)
        client.run("install . --build")

        qmake = load(os.path.join(client.current_folder, "conanbuildinfo.pri"))
        self.assertIn("CONAN_RESDIRS += ", qmake)
        self.assertEqual(qmake.count("CONAN_LIBS += "), 1)
        self.assertIn("CONAN_LIBS_PKG_NAME_WORLD_RELEASE += -lhellor", qmake)
        self.assertIn("CONAN_LIBS_PKG_NAME_WORLD_DEBUG += -lhellod", qmake)
        self.assertIn("CONAN_LIBS_PKG_NAME_WORLD += -lhello", qmake)
        self.assertIn("CONAN_LIBS_RELEASE += -lhellor", qmake)
        self.assertIn("CONAN_LIBS_DEBUG += -lhellod", qmake)
        self.assertIn("CONAN_LIBS += -lhello", qmake)
