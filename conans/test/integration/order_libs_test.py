import os
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.util.files import load


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
    requires = [("LibB/0.1@user/channel", "private"), "LibC/0.1@user/channel"]
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
        self.assertIn("conanfile.py (MyProject/1.0@None/None): Generated conaninfo.txt",
                      self.client.out)

        expected_libs = ['SDL2_ttf', 'freeType', 'SDL2', 'm', 'rt', 'pthread', 'dl',
                         'BZip2', 'LibPNG', 'ZLib']
        conanbuildinfo = load(os.path.join(self.client.current_folder, "conanbuildinfo.txt"))
        libs = os.linesep.join(expected_libs)
        self.assertIn(libs, conanbuildinfo)
        conanbuildinfo = load(os.path.join(self.client.current_folder, "conanbuildinfo.cmake"))
        libs = " ".join(expected_libs)
        self.assertIn(libs, conanbuildinfo)

    def graph_order_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile

class Conan(ConanFile):

        def build(self):
            self.output.info("Lib %s deps: %s" % (self.name, list(self.deps_cpp_info.deps)))
            self.output.info("Lib %s cflags: %s" % (self.name, list(self.deps_cpp_info.cflags)))

        def package_info(self):
            self.cpp_info.cflags = ["%s_flag" % self.name]
        """

        def _export(name, dep=None):
            content = conanfile + "requires = \"%s/1.0@conan/stable\"" % dep if dep else conanfile
            client.save({"conanfile.py": content})
            client.run("create . %s/1.0@conan/stable" % name)
        _export("aaa")
        self.assertIn("Lib aaa deps: %s" % [], client.out)
        self.assertIn("Lib aaa cflags: %s" % [], client.out)
        _export("bbb", "aaa")
        self.assertIn("Lib bbb deps: %s" % ["aaa"], client.out)
        self.assertIn("Lib bbb cflags: %s" % ["aaa_flag"], client.out)
        _export("ccc", "bbb")
        self.assertIn("Lib ccc deps: %s" % ["bbb", "aaa"], client.out)
        self.assertIn("Lib ccc cflags: %s" % ["aaa_flag", "bbb_flag"], client.out)
