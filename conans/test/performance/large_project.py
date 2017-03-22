import unittest
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
import time
from conans.test.utils.tools import TestClient


class PerformanceTest(unittest.TestCase):
    """ NOT really a test, but a helper to profile performance
    FILE name is not "test" so it will not run under unit testing
    """

    def large_project_test(self):
        client = TestClient()
        num = 250
        deep = True  # True for N ... -> 3 -> 2 -> 1 -> 0, False for N -> 0, 3-> 0, 2->0, 1->0
        for i in range(num):
            if i == 0:
                files = cpp_hello_conan_files("Hello0", "0.1", build=False)
            else:
                if not deep:
                    files = cpp_hello_conan_files("Hello%d" % i, "0.1",
                                                  ["Hello0/0.1@lasote/stable"], build=False)
                else:
                    files = cpp_hello_conan_files("Hello%d" % i, "0.1",
                                                  ["Hello%s/0.1@lasote/stable" % (i-1)],
                                                  build=False)

            client.save(files, clean_first=True)
            client.run("export lasote/stable")

        # Now lets depend on it
        if deep:
            files = cpp_hello_conan_files("HelloFinal", "0.1",
                                          ["Hello%s/0.1@lasote/stable" % (num - 1)], build=False)
        else:
            files = cpp_hello_conan_files("HelloFinal", "0.1",
                                          ["Hello%s/0.1@lasote/stable" % (i) for i in range(num)],
                                          build=False)

        client.save(files, clean_first=True)
        t1 = time.time()
        client.run("install --build")
        print("Final time with build %s" % (time.time() - t1))
        t1 = time.time()
        client.run("install")
        print("Final time %s" % (time.time() - t1))
