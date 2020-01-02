import unittest

import semver

from conans import __version__
from conans.client.generators.cmake import CMakeGenerator
from conans.client.generators.cmake_multi import CMakeMultiGenerator
from conans.errors import ConanException
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestBufferConanOutput


class _MockSettings(object):
    build_type = None
    os = None
    os_build = None
    fields = []

    def __init__(self, build_type=None):
        self.build_type = build_type

    @property
    def compiler(self):
        raise ConanException("mock: not available")

    def constraint(self, _):
        return self

    def get_safe(self, name):
        if name == "build_type":
            return self.build_type
        return None

    def items(self):
        return {}


class CMakeGeneratorSentinel(unittest.TestCase):
    """
        In v1.21.1 we introduced a workaround to bypass the `cpp_info.name` for the `cmake` generator, that
        behavior should be reverted and the recipes in `conan-center-index` should be fixed.

        *** These tests HAVE TO pass in v1.22 ***

        Rationale
        https://github.com/conan-io/conan/issues/6269#issuecomment-570182130

        Behavior not to be merged in v1.22
        https://github.com/conan-io/conan/pull/6288

        This test is here just to be sure that the previous PR doesn't reach 1.22, afterwards, this file should
        be removed
    """

    def test_conan_version(self):
        # Remove this TestCase in v1.22
        self.assertEqual(semver.compare(__version__, "1.22.0", loose=False), -1, "Remove this TestCase")

    def _generate_conanfile(self, with_names=None):
        conanfile = ConanFile(TestBufferConanOutput(), None)
        settings = _MockSettings()
        settings.build_type = "Debug"
        conanfile.initialize(settings, EnvValues())

        ref = ConanFileReference.loads("my_pkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.name = "alternate_name"
        if with_names:
            cpp_info.names[with_names] = "alternate_name"
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        return conanfile

    def test_cmake_generator(self):
        conanfile = self._generate_conanfile()
        generator = CMakeGenerator(conanfile)
        content = generator.content
        self.assertIn("CONAN_PKG::alternate_name", content)
        self.assertNotIn("CONAN_PKG::my_pkg", content)

    def test_cmake_multi_generator(self):
        conanfile = self._generate_conanfile()
        generator = CMakeMultiGenerator(conanfile)
        content = generator.content['conanbuildinfo_multi.cmake']
        self.assertIn("CONAN_PKG::alternate_name", content)
        self.assertNotIn("CONAN_PKG::my_pkg", content)

    def test_cmake_generator_with_names(self):
        conanfile = self._generate_conanfile(with_names='cmake')
        generator = CMakeGenerator(conanfile)
        content = generator.content
        self.assertIn("CONAN_PKG::alternate_name", content)
        self.assertNotIn("CONAN_PKG::my_pkg", content)

    def test_cmake_multi_generator_with_names(self):
        conanfile = self._generate_conanfile(with_names='cmake_multi')
        generator = CMakeMultiGenerator(conanfile)
        content = generator.content['conanbuildinfo_multi.cmake']
        self.assertIn("CONAN_PKG::alternate_name", content)
        self.assertNotIn("CONAN_PKG::my_pkg", content)
