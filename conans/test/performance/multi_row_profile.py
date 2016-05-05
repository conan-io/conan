import unittest
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save_files
from conans.test.utils.test_files import temp_folder
import os
import time
from conans.test.tools import TestClient


class PerformanceTest(unittest.TestCase):

    def deep_deps_test(self):
        client = TestClient()
        num = 250
        deep = True
        for i in range(num):
            if i == 0:
                files = cpp_hello_conan_files("Hello0", "0.1")
            else:
                if not deep:
                    files = cpp_hello_conan_files("Hello%d" % i, "0.1",
                                                  ["Hello0/0.1@lasote/stable"])
                else:
                    files = cpp_hello_conan_files("Hello%d" % i, "0.1",
                                                  ["Hello%s/0.1@lasote/stable" % (i-1)])
            files["conanfile.py"] = files["conanfile.py"].replace("build(", "build2(")
            client.save(files, clean_first=True)
            client.run("export lasote/stable")

        # Now lets depend on it
        if deep:
            files = cpp_hello_conan_files("HelloFinal", "0.1",
                                          ["Hello%s/0.1@lasote/stable" % (num - 1)])
        else:
            files = cpp_hello_conan_files("HelloFinal", "0.1",
                                          ["Hello%s/0.1@lasote/stable" % (i) for i in range(num)])
        files["conanfile.py"] = files["conanfile.py"].replace("build(", "build2(")

        client.save(files, clean_first=True)
        t1 = time.time()
        client.run("install --build")
        print("Final time with build %s" % (time.time() - t1))
        t1 = time.time()
        client.run("install")
        print("Final time %s" % (time.time() - t1))
