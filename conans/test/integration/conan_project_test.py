import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load


conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    requires = {deps}
"""


class ConanProjectTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        base_folder = client.current_folder
        project = """[HelloB]
folder: ../B
"""
        client.save({"B/conanfile.py": conanfile.format(deps=None),
                     "A/conanfile.py": conanfile.format(deps="'HelloB/0.1@lasote/stable'"),
                     "A/conan-project.txt": project})

        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -g cmake")
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        print content

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
