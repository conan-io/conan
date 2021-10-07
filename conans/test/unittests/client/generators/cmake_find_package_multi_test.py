import unittest

from mock import Mock

from conans import Settings
from conans.client.generators import CMakeFindPackageMultiGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.test.unittests.client.generators.cmake_test import _MockSettings


class CMakeFindPackageMultiTest(unittest.TestCase):

    def test_cmake_find_package_multi_version(self):
        # https://github.com/conan-io/conan/issues/6908
        settings_mock = _MockSettings(build_type="Debug")
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(settings_mock, EnvValues())
        ref = ConanFileReference.loads("my_pkg/0.1@user/stable")
        cpp_info = CppInfo(ref.name, "")
        cpp_info.version = ref.version
        cpp_info.debug.libs = ["mylib"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        generator = CMakeFindPackageMultiGenerator(conanfile)
        content = generator.content
        config_version = content["my_pkg-config-version.cmake"]
        self.assertIn('set(PACKAGE_VERSION "0.1")', config_version)


def test_cmake_find_package_multi_links_flags():
    # https://github.com/conan-io/conan/issues/8703
    conanfile = ConanFile(Mock(), None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    # https://github.com/conan-io/conan/issues/8811 regression, fix with explicit - instead of /
    cpp_info.sharedlinkflags = ["-NODEFAULTLIB", "-OTHERFLAG"]
    cpp_info.exelinkflags = ["-OPT:NOICF"]
    conanfile.deps_cpp_info.add("mypkg", cpp_info)

    gen = CMakeFindPackageMultiGenerator(conanfile)
    files = gen.content
    d = files["mypkgTarget-release.cmake"]
    assert "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:-OPT:NOICF>" in d
    assert "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:-NODEFAULTLIB;-OTHERFLAG>" in d
    assert "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:-NODEFAULTLIB;-OTHERFLAG>" in d
