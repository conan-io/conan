import os
import platform
import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.tools import TestClient


class BuildEnvironmenTest(unittest.TestCase):

    def test_gcc_environment(self):

        # CREATE A DUMMY LIBRARY WITH GCC (could be generated with other build system)
        mylib = '''
double mean(double a, double b) {
  return (a+b) / 2;
}
'''
        mylibh = '''
double mean(double a, double b);
'''
        conanfile = '''
from conans import ConanFile

class ConanMeanLib(ConanFile):
    name = "Mean"
    version = "0.1"
    exports_sources = "mean*"
    settings = "os", "compiler", "build_type"

    def build(self):
        self.output.info("Running source!")
        self.run("g++ -c -o mean.o mean.c")
        self.run("ar rcs libmean.a mean.o")

    def package(self):
        self.copy("*.h", dst="include")
        self.copy("*.a", dst="lib")

    def package_info(self):
        self.cpp_info.libs.append("mean")
'''

        client = TestClient()
        client.save({CONANFILE: conanfile, "mean.c": mylib, "mean.h": mylibh})
        client.run("export lasote/stable")
        client.run("install Mean/0.1@lasote/stable --build")
        ref = ConanFileReference.loads("Mean/0.1@lasote/stable")
        packages = client.client_cache.packages(ref)

        # Reuse the mean library using the GCCBuildEnvironment
        example = '''
#include "mean.h"
#include <iostream>

int main(){
    std::cout << mean(10, 20) << std::endl;
}
    '''
        reuse = '''
from conans import ConanFile, GCCBuildEnvironment
from conans.tools import environment_append

class ConanReuseLib(ConanFile):

    requires = "Mean/0.1@lasote/stable"
    generators = "gcc"

    def build(self):
        build_env = GCCBuildEnvironment(self)
        with environment_append(build_env.vars):
            self.run("g++ example.c @conanbuildinfo.gcc -o mean_exe ")
        self.run("./mean_exe");
'''

        client.save({CONANFILE: reuse, "example.c": example})
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("15", client.user_io.out)
