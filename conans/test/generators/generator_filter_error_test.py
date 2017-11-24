import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os


class MultiGeneratorFilterErrorTest(unittest.TestCase):

    def regression_test(self):
        # Possible regression of: https://github.com/conan-io/conan/pull/1719#issuecomment-339137460
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
    def package(self):
        self.copy("*", dst="include")
""", "header.h": ""})
        client.run("create Pkg/0.1@user/stable")
        client.save({"conanfile.txt": "[requires]\nPkg/0.1@user/stable\n"
                     "[generators]\nycm\ncmake\ntxt\ngcc\n"}, clean_first=True)
        client.run("install .")

        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        txt = load(os.path.join(client.current_folder, "conanbuildinfo.txt"))
        gcc = load(os.path.join(client.current_folder, "conanbuildinfo.gcc"))
        ycm = load(os.path.join(client.current_folder, ".ycm_extra_conf.py"))
        self.assertIn("Pkg/0.1/user/stable/package/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/include",
                      cmake)
        self.assertIn("Pkg/0.1/user/stable/package/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/include",
                      txt)
        self.assertIn("Pkg/0.1/user/stable/package/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/include",
                      gcc)
        self.assertIn("Pkg/0.1/user/stable/package/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/include",
                      ycm.replace("\\", "/"))
