import unittest
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save_files
from conans.test.utils.test_files import temp_folder
import os
import time


def run(command):
    retcode = os.system(command)
    if retcode != 0:
        raise Exception("Error while executing:\n\t %s" % command)


class PerformanceTest(unittest.TestCase):

    def deep_deps_test(self):
        num = 5
        for i in range(num):
            if i == 0:
                files = cpp_hello_conan_files("Hello0", "0.1")
            else:
                files = cpp_hello_conan_files("Hello%d" % i, "0.1",
                                              ["Hello%s/0.1@lasote/stable" % (i-1)])
            files["conanfile.py"] = files["conanfile.py"].replace("build(", "build2(")
            t_folder = temp_folder()
            save_files(t_folder, files)
            try:
                old_folder = os.getcwd()
                os.chdir(t_folder)
                run("conan export lasote/stable > null")
            finally:
                os.chdir(old_folder)

        # Now lets depend on it
        files = cpp_hello_conan_files("HelloFinal", "0.1", ["Hello%s/0.1@lasote/stable" % (num-1)])
        files["conanfile.py"] = files["conanfile.py"].replace("build(", "build2(")
        t_folder = temp_folder()
        save_files(t_folder, files)
        try:
            old_folder = os.getcwd()
            os.chdir(t_folder)
            t1 = time.time()
            run("conan install --build")
            print("Final time with build %s" % (time.time() - t1))
            t1 = time.time()
            run("conan install")
            print("Final time %s" % (time.time() - t1))
        finally:
            print("Final time %s" % (time.time() - t1))
            os.chdir(old_folder)
