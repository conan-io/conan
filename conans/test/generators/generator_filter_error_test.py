import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os


class MultiGeneratorFilterErrorTest(unittest.TestCase):

    def test(self):
        # Possible regression of: https://github.com/conan-io/conan/pull/1719#issuecomment-339137460
        # https://github.com/conan-io/conan/issues/2149
        client = TestClient()
        llvm = '''
from conans import ConanFile
class ConanLib(ConanFile):
    generators = "cmake", "visual_studio", "qmake", "ycm"
    exports_sources = "*"
    def package(self):
        self.copy("*")
    def package_info(self):
        self.cpp_info.includedirs = ["include", "include/c++/v1"]
'''

        client.save({"conanfile.py": llvm,
                     "include/file.h": "",
                     "include/c++/v1/file2.h": ""})
        client.run("create . llvm/5.0@user/channel")
        test = '''
from conans import ConanFile
class ConanLib(ConanFile):
    def test(self):
        pass
'''
        myprofile = """[build_requires]
llvm/5.0@user/channel
"""
        client.save({"conanfile.py": llvm,
                     "include/file3.h": "",
                     "include/c++/v1/file4.h": "",
                     "test_package/conanfile.py": test,
                     "myprofile": myprofile}, clean_first=True)
        client.run("create . MyLib/0.1@user/channel -pr=myprofile")
        content = load(os.path.join(client.current_folder,
                                    "test_package/build/91852f76fac8dd11832a54cf197288f5fd7d18f4"
                                    "/conanbuildinfo.txt"))
        self.assertIn(".conan/data/MyLib/0.1/user/channel/package/"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/include",
                      content)
