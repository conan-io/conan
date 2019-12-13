
import os
import platform
import unittest
import textwrap
from nose.plugins.attrib import attr
from parameterized import parameterized

from conans import MSBuild, tools
from conans.client.runner import ConanRunner
from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.test.utils.tools import TestClient, TestBufferConanOutput
from conans.test.utils.visual_project_files import get_vs_project_files


class MultiGeneratorsTestCase(unittest.TestCase):

    @parameterized.expand([("cmake_find_package_multi",), ("visual_studio_multi", ), ("cmake_multi", )])
    def test_no_build_type_test(self, generator):
        client = TestClient()
        client.run("new req/version")
        client.run("create .")

        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            project(consumer)
            find_package(req)
            message(STATUS "hello found: ${{hello_FOUND}}")
        """)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                settings = "os", "arch", "compiler"
                requires = "req/version"
                generators = "{generator}"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """.format(generator=generator))

        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .", assert_error=True)
        self.assertIn("ERROR: 'settings.build_type' doesn't exist", client.out)
