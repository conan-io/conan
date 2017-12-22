import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
from conans.util.files import load
import os


class OrderLibsTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

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

        expected_libs = ['SDL2_ttf', 'SDL2', 'rt', 'pthread', 'dl', 'freeType',
                         'BZip2', 'LibPNG', 'm', 'ZLib']
        conanbuildinfo = load(os.path.join(self.client.current_folder, "conanbuildinfo.txt"))
        libs = os.linesep.join(expected_libs)
        self.assertIn(libs, conanbuildinfo)
        conanbuildinfo = load(os.path.join(self.client.current_folder, "conanbuildinfo.cmake"))
        libs = " ".join(expected_libs)
        self.assertIn(libs, conanbuildinfo)
