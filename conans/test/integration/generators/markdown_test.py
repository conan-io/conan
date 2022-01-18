import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.client.tools.files import load


class MarkDownGeneratorTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Generator markdown to be updated with new transitive_deps visit")
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
        client.run("create . --name=bar --version=0.1.0 --user=user --channel=testing")
        client.run("install --reference=bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("Generates the file FindFooBar.cmake", content)
        self.assertIn("find_package(FooBar)", content)

    @pytest.mark.xfail(reason="Generator markdown to be updated with new transitive_deps visit")
    def test_with_build_modules(self):
        conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        exports_sources = 'bm.cmake'
                        def package(self):
                            self.copy('bm.cmake', dst='lib/cmake')

                        def package_info(self):
                            self.cpp_info.filenames['cmake_find_package'] = 'FooBar'
                            self.cpp_info.names['cmake_find_package'] = 'foobar'
                            self.cpp_info.names['cmake_find_package_multi'] = 'foobar_multi'
                            self.cpp_info.names['pkg_config'] = 'foobar_cfg'
                            self.cpp_info.build_modules['cmake_find_package'] = ['lib/cmake/bm.cmake']
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "bm.cmake": "Content of build_module" })
        client.run("create . --name=bar --version=0.1.0 --user=user --channel=testing")
        client.run("install --reference=bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("Generates the file FindFooBar.cmake", content)
        self.assertIn("* `lib/cmake/bm.cmake`", content)
        self.assertIn("Content of build_module", content)
