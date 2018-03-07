import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load, mkdir
import re
from conans.test.utils.cpp_test_files import cpp_hello_conan_files


conanfile = """from conans import ConanFile
import os
class Pkg(ConanFile):
    requires = {deps}
    generators = "cmake"
    exports_sources = "*.h"
    def build(self):
        assert os.path.exists("conanbuildinfo.cmake")
    def package(self):
        self.copy("*.h", dst="include")
    def package_id(self):
        self.info.header_only()
"""


class ConanProjectTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        base_folder = client.current_folder
        project = """[HelloB]
folder: ../B
[HelloC]
folder: ../C
"""
        client.save({"C/conanfile.py": conanfile.format(deps=None),
                     "C/header_c.h": "header-c!",
                     "B/conanfile.py": conanfile.format(deps="'HelloC/0.1@lasote/stable'"),
                     "B/header_b.h": "header-b!",
                     "A/conanfile.py": conanfile.format(deps="'HelloB/0.1@lasote/stable'"),
                     "A/conan-project.txt": project})

        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -g cmake --build")
        client.run("search")
        self.assertIn("There are no packages", client.out)
        # Check A
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        include_dirs_hellob = re.search('set\(CONAN_INCLUDE_DIRS_HELLOB "(.*)"\)', content).group(1)
        self.assertEqual("header-b!", load(os.path.join(include_dirs_hellob, "header_b.h")))
        include_dirs_helloc = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual("header-c!", load(os.path.join(include_dirs_helloc, "header_c.h")))

        # Check B
        content = load(os.path.join(base_folder, "B/build/conanbuildinfo.cmake"))
        include_dirs_helloc2 = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc2, include_dirs_helloc)

    def build_test(self):
        client = TestClient()
        c_files = cpp_hello_conan_files(name="HelloC")
        client.save(c_files, path=os.path.join(client.current_folder, "C"))
        b_files = cpp_hello_conan_files(name="HelloB", deps=["HelloC/0.1@lasote/stable"])
        client.save(b_files, path=os.path.join(client.current_folder, "B"))

        base_folder = client.current_folder
        project = """[HelloB]
folder: ../B
[HelloC]
folder: ../C
"""
        a_files = cpp_hello_conan_files(name="HelloA", deps=["HelloB/0.1@lasote/stable"])
        a_files["conan-project.txt"] = project
        client.save(a_files, path=os.path.join(client.current_folder, "A"))

        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -g cmake --build")
        print client.out

        # Check A
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))

        include_dirs_hellob = re.search('set\(CONAN_INCLUDE_DIRS_HELLOB "(.*)"\)', content).group(1)
        self.assertIn("void helloHelloB();", load(os.path.join(include_dirs_hellob, "helloHelloB.h")))
        include_dirs_helloc = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertIn("void helloHelloC();", load(os.path.join(include_dirs_helloc, "helloHelloC.h")))

        # Check B
        content = load(os.path.join(base_folder, "B/build/conanbuildinfo.cmake"))
        include_dirs_helloc2 = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc2, include_dirs_helloc)

        client.run("build .")
        print client.out
        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        print client.current_folder
        print client.out

    def basic_test2(self):
        client = TestClient()
        base_folder = client.current_folder
        cache_folder = os.path.join(client.client_cache.conan_folder, "data").replace("\\", "/")

        for pkg in "A", "B", "C", "D", "E":
            deps = ["Hello%s/0.1@lasote/stable" % (chr(ord(pkg)+1))] if pkg != "E" else None
            deps = ", ".join('"%s"' % d for d in deps) if deps else "None"
            files = {"conanfile.py": conanfile.format(deps=deps)}
            client.current_folder = os.path.join(base_folder, pkg)
            client.save(files)
        for pkg in reversed(["B", "C", "D", "E"]):
            client.current_folder = os.path.join(base_folder, pkg)
            client.run("create . Hello%s/0.1@lasote/stable" % pkg)

        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -g cmake")
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        content = content.replace(cache_folder, "")

        self.assertIn('set(CONAN_HELLOB_ROOT "/HelloB/0.1/lasote/stable/package/'
                      '859b7e9ee613cc57acbe7ff443792122ace64268")',
                      content)
        self.assertIn('set(CONAN_HELLOC_ROOT "/HelloC/0.1/lasote/stable/package/'
                      '8cc772399656f6e830290e4d202f063b7d6470d4")',
                      content)
        self.assertIn('set(CONAN_HELLOD_ROOT "/HelloD/0.1/lasote/stable/package/'
                      '767f6b60271697e9db340c9482a1bd665eaa59e8")',
                      content)
        self.assertIn('set(CONAN_HELLOE_ROOT "/HelloE/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)

        client.save({"conan-project.txt": "HelloC: MyPATH"})
        client.run("install . -g cmake")
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        content = content.replace(cache_folder, "")

        self.assertIn('set(CONAN_HELLOB_ROOT "/HelloB/0.1/lasote/stable/package/'
                      '859b7e9ee613cc57acbe7ff443792122ace64268")',
                      content)
        self.assertIn('set(CONAN_HELLOC_ROOT "MyPATH")',
                      content)
        self.assertIn('set(CONAN_HELLOD_ROOT "/HelloD/0.1/lasote/stable/package/'
                      '767f6b60271697e9db340c9482a1bd665eaa59e8")',
                      content)
        self.assertIn('set(CONAN_HELLOE_ROOT "/HelloE/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)
