import textwrap
import unittest

from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.utils.tools import TestClient


class TestPackageInfo(unittest.TestCase):

    def package_info_called_in_local_cache_test(self):
        client = TestClient()
        conanfile_tmp = '''
from conans import ConanFile
import os

class HelloConan(ConanFile):
    name = "%s"
    version = "1.0"
    build_policy = "missing"
    options = {"switch": ["1",  "0"]}
    default_options = "switch=0"
    %s

    def build(self):
        self.output.warn("Env var MYVAR={0}.".format(os.getenv("MYVAR", "")))

    def package_info(self):
        if self.options.switch == "0": 
            self.env_info.MYVAR = "foo"
        else:
            self.env_info.MYVAR = "bar"

'''
        for index in range(4):
            requires = "requires = 'Lib%s/1.0@conan/stable'" % index if index > 0 else ""
            conanfile = conanfile_tmp % ("Lib%s" % (index + 1), requires)
            client.save({CONANFILE: conanfile}, clean_first=True)
            client.run("create . conan/stable")

        txt = "[requires]\nLib4/1.0@conan/stable"
        client.save({CONANFILE_TXT: txt}, clean_first=True)
        client.run("install . -o *:switch=1")
        self.assertIn("Lib1/1.0@conan/stable: WARN: Env var MYVAR=.", client.out)
        self.assertIn("Lib2/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)
        self.assertIn("Lib3/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)
        self.assertIn("Lib4/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)

        client.run("install . -o *:switch=0 --build Lib3")
        self.assertIn("Lib3/1.0@conan/stable: WARN: Env var MYVAR=foo", client.out)

    def package_info_components_test(self):
        dep = textwrap.dedent("""
        from conans import ConanFile

        class Dep(ConanFile):
            exports_sources = "*"

            def package(self):
                self.copy("*")

            def package_info(self):
                self.cpp_info.name = "Boost"
                self.cpp_info.includedirs = ["boost"]
                self.cpp_info["Accumulators"].includedirs = ["boost/accumulators"]
                self.cpp_info["Accumulators"].lib = "libaccumulators"
                self.cpp_info["Containers"].includedirs = ["boost/containers"]
                self.cpp_info["Containers"].lib = "libcontainers"
                self.cpp_info["Containers"].deps = ["Accumulators"]
                self.cpp_info["SuperContainers"].includedirs = ["boost/supercontainers"]
                self.cpp_info["SuperContainers"].lib = "libsupercontainers"
                self.cpp_info["SuperContainers"].deps = ["Containers"]
        """)
        consumer = textwrap.dedent("""
        from conans import ConanFile

        class Consumer(ConanFile):
            requires = "dep/1.0@us/ch"

            def build(self):
                acc_includes = self.deps_cpp_info["dep"]["Accumulators"].includedirs
                con_include = self.deps_cpp_info["dep"]["Containers"].includedirs
                sup_include = self.deps_cpp_info["dep"]["SuperContainers"].includedirs
                self.output.info("Name: %s" % self.deps_cpp_info["dep"].name)
                self.output.info("Accumulators: %s" % acc_includes)
                self.output.info("Containers: %s" % con_include)
                self.output.info("SuperContainers: %s" % sup_include)
                self.output.info("LIBS: %s" % self.deps_cpp_info["dep"].libs)
                print("INCLUDE_PATHS: %s" % self.deps_cpp_info["dep"].include_paths)
                print("INCLUDE_PATHS: %s" % self.deps_cpp_info.include_paths)
        """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep, "conanfile_consumer.py": consumer,
                     "boost/boost.h": "",
                     "boost/accumulators/accumulators.h": "",
                     "boost/containers/containers.h": "",
                     "boost/supercontainers/supercontainers.h": ""})
        client.run("create conanfile_dep.py dep/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch")
        self.assertIn("Name: Boost", client.out)
        self.assertIn("Accumulators: ['boost', 'boost/accumulators']", client.out)
        self.assertIn("Containers: ['boost', 'boost/containers']", client.out)
        self.assertIn("SuperContainers: ['boost', 'boost/supercontainers']", client.out)
        self.assertIn("LIBS: ['libaccumulators', 'libcontainers', 'libsupercontainers']", client.out)
