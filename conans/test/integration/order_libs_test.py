import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
from conans.util.files import load
import os


class OrderLibsTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def private_order_test(self):
        # https://github.com/conan-io/conan/issues/3006
        client = TestClient()
        conanfile = """from conans import ConanFile
class LibBConan(ConanFile):
    def package_info(self):
        self.cpp_info.libs = ["LibC"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . LibC/0.1@user/channel")

        conanfile = """from conans import ConanFile
class LibCConan(ConanFile):
    requires = "LibC/0.1@user/channel"
    def package_info(self):
        self.cpp_info.libs = ["LibB"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . LibB/0.1@user/channel")

        conanfile = """from conans import ConanFile
class LibCConan(ConanFile):
    requires = ("LibB/0.1@user/channel", "private"), "LibC/0.1@user/channel"
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g cmake")
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS LibB LibC ${CONAN_LIBS})", conanbuildinfo)
        # Change private
        conanfile = """from conans import ConanFile
class LibCConan(ConanFile):
    requires = "LibB/0.1@user/channel", ("LibC/0.1@user/channel", "private")
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g cmake")
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS LibB LibC ${CONAN_LIBS})", conanbuildinfo)
        # Change order
        conanfile = """from conans import ConanFile
class LibCConan(ConanFile):
    requires = ("LibC/0.1@user/channel", "private"), "LibB/0.1@user/channel"
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g cmake")
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS LibB LibC ${CONAN_LIBS})", conanbuildinfo)
        # Change order
        conanfile = """from conans import ConanFile
class LibCConan(ConanFile):
    requires = "LibC/0.1@user/channel", ("LibB/0.1@user/channel", "private")
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g cmake")
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS LibB LibC ${CONAN_LIBS})", conanbuildinfo)

    def _export(self, name, deps=None, export=True):
        def _libs():
            if name == "LibPNG":
                libs = '"m"'
            elif name == "SDL2":
                libs = '"m", "rt", "pthread", "dl"'
            else:
                libs = ""
            return libs
        deps = ", ".join(['"%s/1.0@lasote/stable"' % d for d in deps or []]) or '""'
        conanfile = """
from conans import ConanFile, CMake

class HelloReuseConan(ConanFile):
    name = "%s"
    version = "1.0"
    requires = %s
    generators = "txt", "cmake"

    def package_info(self):
        self.cpp_info.libs = ["%s", %s]
""" % (name, deps, name, _libs())

        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")

    def reuse_test(self):
        self._export("ZLib")
        self._export("BZip2")
        self._export("SDL2", ["ZLib"])
        self._export("LibPNG", ["ZLib"])
        self._export("freeType", ["BZip2", "LibPNG"])
        self._export("SDL2_ttf", ["freeType", "SDL2"])
        self._export("MyProject", ["SDL2_ttf"], export=False)

        self.client.run("install . --build missing")
        self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)

        expected_libs = ['SDL2_ttf', 'freeType', 'SDL2', 'rt', 'pthread', 'dl',
                         'BZip2', 'LibPNG', 'm', 'ZLib']
        conanbuildinfo = load(os.path.join(self.client.current_folder, "conanbuildinfo.txt"))
        libs = os.linesep.join(expected_libs)
        self.assertIn(libs, conanbuildinfo)
        conanbuildinfo = load(os.path.join(self.client.current_folder, "conanbuildinfo.cmake"))
        libs = " ".join(expected_libs)
        self.assertIn(libs, conanbuildinfo)
