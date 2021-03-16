import textwrap
import unittest

from conans.test.utils.tools import TestClient
from conans.client.tools.files import load


class MarkDownGeneratorTest(unittest.TestCase):

    def test_cmake_find_filename(self):
        conanfile = textwrap.dedent("""
                    from conans import ConanFile
                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.filenames['cmake_find_package'] = 'FooBar'
                            self.cpp_info.names['cmake_find_package'] = 'foobar'
                            self.cpp_info.names['cmake_find_package_multi'] = 'foobar_multi'
                            self.cpp_info.names['pkg_config'] = 'foobar_cfg'
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("Generates the file FindFooBar.cmake", content)
        self.assertIn("find_package(FooBar)", content)
